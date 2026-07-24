import os
import re

# ================= 配置区域 =================
# 配置：文章所在的根目录，脚本会递归遍历该目录
POSTS_DIR = 'content/post'

def fix_markdown_files():
    """
    主入口函数：遍历目录并处理文件
    """
    print(">>> 正在执行 V10.0 标准格式版 (强制 :--- 左对齐 + 插入空行)...")

    # os.walk 递归遍历目录
    for root, dirs, files in os.walk(POSTS_DIR):
        for file in files:
            # 只处理 .md 文件，且忽略以 _index 开头的文件（通常是 Hugo 的列表页配置）
            if file.endswith('.md') and not file.startswith('_index'):
                filepath = os.path.join(root, file)
                process_file(filepath)

def process_file(filepath):
    """
    核心处理逻辑：读取单个文件 -> 清洗 -> 提取元数据 -> 重组表格 -> 保存
    """
    try:
        # 使用 utf-8 读取文件
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"读取失败: {filepath} - {e}")
        return

    is_modified = False # 标记文件是否被修改过

    # 1. 【清洗】去除零宽空格 (Zero-width space)
    # 这种字符通常来自于从网页复制粘贴，会导致编辑器或解析器报错
    if '\u200b' in content:
        content = content.replace('\u200b', '')
        is_modified = True

    # 分割 Front Matter (头部 YAML) 和正文 (Body)
    # split('---', 2) 会切分成 ['', 'Front Matter内容', '正文内容']
    parts = content.split('---', 2)
    if len(parts) < 3: return # 如果不是标准的 Hugo/Hexo 格式，跳过
    front_matter, body = parts[1], parts[2]

    # 2. 【表格处理】重构表格 + 修复表格前的空行
    new_body_lines = []
    body_lines = body.split('\n')

    in_table = False    # 状态机：是否正在读取表格
    table_buffer = []   # 缓存表格行

    for i, line in enumerate(body_lines):
        stripped = line.strip()

        # 判断当前行是否是表格行 (以 | 开头)
        if stripped.startswith('|'):
            if not in_table:
                # === 发现表格开始 ===

                # 【关键修复】检查上一行是否为空行
                # Markdown 标准要求表格前必须有空行，否则可能无法渲染
                if new_body_lines and new_body_lines[-1].strip() != "":
                    new_body_lines.append("") 

                in_table = True
                table_buffer = []

            # 将当前行加入表格缓存
            table_buffer.append(line)
        else:
            if in_table:
                # === 表格结束 ===
                # 调用重构函数处理刚才缓存的表格
                reconstructed = reconstruct_table(table_buffer)

                # 检查重构前后内容是否一致，不一致说明表格被优化了
                if "".join(reconstructed) != "".join(table_buffer):
                    print(f"  [表格] 重构为标准格式: {os.path.basename(filepath)}")
                    is_modified = True

                # 将重构后的表格行加入新正文
                new_body_lines.extend(reconstructed)

                # 重置状态
                in_table = False
                table_buffer = []

                # 当前这一行不是表格，直接加入（例如表格后的文字）
                new_body_lines.append(line)
            else:
                # 普通文本行，直接加入
                new_body_lines.append(line)

    # 处理文件以表格结尾的情况 (EOF)
    if in_table and table_buffer:
        reconstructed = reconstruct_table(table_buffer)
        if "".join(reconstructed) != "".join(table_buffer):
             is_modified = True
        new_body_lines.extend(reconstructed)

    # 如果在步骤2中修改了内容，更新 body 变量
    if is_modified:
        body = '\n'.join(new_body_lines)

    # 3. 【封面图提取】
    # 如果 Front Matter 里没有 image 字段
    if not re.search(r'^image:\s*http', front_matter, re.MULTILINE):
        # 查找正文中的第一张网络图片 ![] (http...)
        match = re.search(r'!\[.*?\]\((http.*?)\)', body)
        if match:
            # 清理旧的 image 字段（如果有的话）
            front_matter = re.sub(r'^image:.*\{\{.*\}\}.*$', '', front_matter, flags=re.MULTILINE).strip()
            # 添加新的 image 字段
            front_matter += f'\nimage: {match.group(1)}'
            # 从正文中删除这张图片的代码
            body = body.replace(match.group(0), '', 1) 
            is_modified = True

    # 4. 【标题提取】
    # 查找所有的 H1 标题 (# Title)
    h1_matches = list(re.finditer(r'^\s*#\s+(.+?)\s*$', body, re.MULTILINE))
    target_title = ""

    # 逻辑：有些博客习惯第一个 # 是站点名，第二个 # 才是文章名
    if len(h1_matches) >= 2: 
        target_title = h1_matches[1].group(1).strip()
    elif len(h1_matches) == 1: 
        target_title = h1_matches[0].group(1).strip()

    if target_title:
        # 转义标题中的双引号，防止 YAML 语法错误
        safe_title = target_title.replace('"', '\\"')

        # 如果 Front Matter 已有 title，替换它；否则追加
        if re.search(r'^title:', front_matter, re.MULTILINE):
            front_matter = re.sub(r'^title:.*$', f'title: "{safe_title}"', front_matter, flags=re.MULTILINE)
        else:
            front_matter += f'\ntitle: "{safe_title}"'

        # 从正文中删除所有的 H1 标题，避免重复显示
        body = re.sub(r'^\s*#\s+(.+?)\s*$', '', body, flags=re.MULTILINE) 
        is_modified = True

    # 5. 【标签提取】
    # 如果 Front Matter 没有 tags
    if not re.search(r'^tags:', front_matter, re.MULTILINE):
        # 在正文中查找 "Tags: a, b, c" 或 "标签: a, b, c"
        match = re.search(r'^(?:Tags|标签)[:：]\s*(.*)$', body, re.MULTILINE | re.IGNORECASE)
        if match:
            # 按逗号、顿号、空格分割标签
            items = [t.strip() for t in re.split(r'[,，、\s]+', match.group(1)) if t.strip()]
            if items:
                # 格式化为 YAML 列表格式
                front_matter += "\ntags:\n" + "\n".join([f"  - {t}" for t in items])
                # 从正文中删除这一行
                body = body.replace(match.group(0), '')
                is_modified = True

    # 6. 【保存文件】
    if is_modified:
        # 将正文中连续的3个以上换行符替换为2个（去除多余空行）
        body = re.sub(r'\n{3,}', '\n\n', body.strip())
        # 重新拼接文件内容
        new_content = f'---{front_matter}\n---\n\n{body}'
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)

def reconstruct_table(lines):
    """
    表格重构核心逻辑：
    1. 解析 Markdown 表格为矩阵
    2. 删除没有任何内容的列
    3. 重新生成表格字符串，强制使用 :--- 左对齐
    """
    if not lines: return lines

    # 1. 过滤有效行：排除掉原本的分隔线行（例如 |--|--|）
    # 这一步会把原本的对齐方式丢弃，准备重新生成
    content_lines = []
    for line in lines:
        # 正则含义：如果行只包含 空格、|、-、:、+，则认为是分隔线，不存入 content_lines
        if not re.match(r'^[\s\|\-\:\–\—\+]+$', line.strip()):
            content_lines.append(line)

    if not content_lines: return lines

    # 2. 解析矩阵
    matrix = []
    for line in content_lines:
        # 按 | 切割单元格
        cells = line.strip().split('|')
        # 去除首尾因为 split 产生的空元素 (比如 "| a | b |" split后首尾会有空字符)
        if len(cells) > 0 and cells[0].strip() == '': cells.pop(0)
        if len(cells) > 0 and cells[-1].strip() == '': cells.pop(-1)
        matrix.append(cells)

    # 3. 识别有效列（如果某一列在所有行里都是空的，就丢弃该列）
    max_cols = 0
    if matrix:
        max_cols = max(len(row) for row in matrix)

    cols_to_keep = []
    for c in range(max_cols):
        is_empty = True
        for row in matrix:
            if c < len(row) and row[c].strip():
                is_empty = False
                break
        if not is_empty:
            cols_to_keep.append(c)

    # 4. 重组表格文本
    new_lines = []

    # A. 写入表头 (第一行)
    header_row = matrix[0]
    new_header = []
    for c in cols_to_keep:
        cell = header_row[c].strip() if c < len(header_row) else "" 
        new_header.append(cell)
    new_lines.append("| " + " | ".join(new_header) + " |")

    # B. 生成分隔线 (强制左对齐 :---)
    # 如果你想改对齐方式，改这里，例如 ":-:" 是居中
    separators = [":---"] * len(cols_to_keep)
    new_lines.append("| " + " | ".join(separators) + " |")

    # C. 写入数据行 (从第二行开始)
    for row in matrix[1:]:
        new_data = []
        for c in cols_to_keep:
            cell = row[c].strip() if c < len(row) else "" 
            new_data.append(cell)
        new_lines.append("| " + " | ".join(new_data) + " |")

    return new_lines

if __name__ == "__main__":
    fix_markdown_files()
    print(">>> V10.0 处理完成")
