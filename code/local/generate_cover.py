#!/usr/bin/env python3
"""
Agent技术笔记 — 公众号封面图生成器
用法：
    python generate_cover.py "ReAct深度解析"
    python generate_cover.py "Agent技术全景图" --subtitle "从概念到落地的完整技术栈"
    python generate_cover.py "Memory模块设计" --tag "实战案例"
    python generate_cover.py "LangGraph实战" --output custom_name.png
"""
import os
import sys
import math
import argparse
import random

from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ── 尺寸（微信公众号头条封面标准 2.35:1）───────────────
W, H = 900, 383

# ── 颜色体系（和头像一致）─────────────────────────────────
BG_TOP      = (10, 15, 35)       # 背景顶部深蓝
BG_BOTTOM   = (20, 30, 60)       # 背景底部稍亮
HEX_COLOR   = (30, 55, 90)       # 装饰六边形
GRID_COLOR  = (25, 40, 70)       # 网格线
NODE_COLOR  = (34, 211, 238)      # 青色节点
ACCENT1     = (34, 211, 238)      # 青
ACCENT2     = (167, 139, 250)     # 紫
TEXT_WHITE   = (240, 245, 255)    # 标题白色
TEXT_DIM     = (120, 140, 170)    # 副标题/标签灰
BRAND_COLOR = (60, 80, 120)      # 品牌名颜色

# ── 字体路径 ──────────────────────────────────────────────
FONT_CANDIDATES_CN = [
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
]

FONT_CANDIDATES_EN = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/HelveticaNeue-Bold.ttf",
    "/System/Library/Fonts/Helvetica-Bold.ttf",
]


def find_font(candidates, size, index=0):
    """尝试加载字体，返回 (font, path) 或 (None, None)"""
    for fp in candidates:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size=size, index=index)
            except Exception:
                continue
    return ImageFont.load_default(), None


def draw_hexagon(draw, cx, cy, r, color, width=1):
    """绘制六边形"""
    pts = []
    for i in range(6):
        angle = math.radians(60 * i - 30)
        px = cx + r * math.cos(angle)
        py = cy + r * math.sin(angle)
        pts.append((px, py))
    for i in range(6):
        draw.line([pts[i], pts[(i + 1) % 6]], fill=color, width=width)
    return pts


def draw_node(draw, x, y, r, color, glow=True):
    """绘制发光节点"""
    if glow:
        for i in range(3):
            alpha_r = r + (3 - i) * 3
            glow_color = tuple(max(0, min(255, c // (i + 2))) for c in color)
            draw.ellipse([x - alpha_r, y - alpha_r, x + alpha_r, y + alpha_r], fill=glow_color)
    draw.ellipse([x - r, y - r, x + r, y + r], fill=color)


def draw_connection(draw, x1, y1, x2, y2, color, width=1):
    """绘制两点之间的连接线"""
    draw.line([(x1, y1), (x2, y2)], fill=color, width=width)


def auto_split_text(text, font, max_width, draw):
    """将文本自动分行，适配最大宽度"""
    lines = []
    current_line = ""
    for char in text:
        test_line = current_line + char
        bbox = draw.textbbox((0, 0), test_line, font=font)
        if bbox[2] - bbox[0] > max_width:
            if current_line:
                lines.append(current_line)
            current_line = char
        else:
            current_line = test_line
    if current_line:
        lines.append(current_line)
    return lines


def generate_cover(title, subtitle=None, tag=None, output_path=None, seed=None):
    """生成封面图"""
    if seed is not None:
        random.seed(seed)
    else:
        random.seed(42)

    # ── 创建画布 ─────────────────────────────────────────
    img = Image.new("RGBA", (W, H))
    draw = ImageDraw.Draw(img)

    # ── 背景渐变 ─────────────────────────────────────────
    for y in range(H):
        t = y / H
        r = int(BG_TOP[0] + (BG_BOTTOM[0] - BG_TOP[0]) * t)
        g = int(BG_TOP[1] + (BG_BOTTOM[1] - BG_TOP[1]) * t)
        b = int(BG_TOP[2] + (BG_BOTTOM[2] - BG_TOP[2]) * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b, 255))

    # ── 背景网格 ─────────────────────────────────────────
    grid_spacing = 60
    for x in range(0, W, grid_spacing):
        draw.line([(x, 0), (x, H)], fill=GRID_COLOR + (40,), width=1)
    for y in range(0, H, grid_spacing):
        draw.line([(0, y), (W, y)], fill=GRID_COLOR + (40,), width=1)

    # ── 装饰六边形（右侧区域）───────────────────────────
    hex_positions = [
        (W - 80, 65, 40),
        (W - 140, 160, 50),
        (W - 50, 230, 30),
        (W - 120, 310, 45),
        (W - 200, 100, 25),
        (W - 180, 260, 35),
        (70, 320, 25),
        (30, 50, 20),
    ]
    for hx, hy, hr in hex_positions:
        alpha = random.randint(30, 80)
        draw_hexagon(draw, hx, hy, hr, HEX_COLOR + (alpha,), width=2)

    # ── 装饰节点和连线 ──────────────────────────────────
    node_positions = [
        (W - 100, 120, 4, ACCENT1),
        (W - 160, 220, 3, ACCENT2),
        (W - 70, 280, 3, ACCENT1),
        (W - 130, 80, 2, ACCENT2),
        (60, 80, 2, ACCENT1),
        (90, 280, 2, ACCENT2),
    ]
    for nx, ny, nr, nc in node_positions:
        draw_node(draw, nx, ny, nr, nc, glow=True)

    # 连接线
    connections = [
        (W - 100, 120, W - 160, 220),
        (W - 160, 220, W - 70, 280),
        (W - 130, 80, W - 100, 120),
    ]
    for x1, y1, x2, y2 in connections:
        draw_connection(draw, x1, y1, x2, y2, HEX_COLOR + (60,), width=1)

    # ── 左侧装饰竖线 ────────────────────────────────────
    accent_x = 55
    for i in range(4):
        y_start = 50 + i * 70
        alpha = 40 + i * 15
        draw.line([(accent_x, y_start), (accent_x, y_start + 35)],
                  fill=ACCENT1 + (alpha,), width=2)

    # ── 标签（右上角）────────────────────────────────────
    if tag:
        tag_font = find_font(FONT_CANDIDATES_CN, 22)
        tag_bbox = draw.textbbox((0, 0), tag, font=tag_font)
        tag_w = tag_bbox[2] - tag_bbox[0] + 20
        tag_h = tag_bbox[3] - tag_bbox[1] + 10
        tag_x = W - tag_w - 40
        tag_y = 30
        # 标签背景
        draw.rounded_rectangle(
            [(tag_x, tag_y), (tag_x + tag_w, tag_y + tag_h)],
            radius=4,
            fill=ACCENT1 + (30,),
            outline=ACCENT1 + (80,),
            width=1
        )
        draw.text((tag_x + 10, tag_y + 5), tag, font=tag_font, fill=ACCENT1)

    # ── 标题文字 ─────────────────────────────────────────
    title_font_size = 56
    title_font = find_font(FONT_CANDIDATES_CN, title_font_size)

    # 自适应字号：如果标题太长自动缩小
    max_title_width = W - 250  # 留出右侧装饰区域
    test_bbox = draw.textbbox((0, 0), title, font=title_font)
    while test_bbox[2] - test_bbox[0] > max_title_width and title_font_size > 30:
        title_font_size -= 2
        title_font = find_font(FONT_CANDIDATES_CN, title_font_size)
        test_bbox = draw.textbbox((0, 0), title, font=title_font)

    # 自动分行
    lines = auto_split_text(title, title_font, max_title_width, draw)
    line_height = int(title_font_size * 1.5)

    # 标题区域垂直居中（偏上一点）
    total_text_height = len(lines) * line_height
    title_start_y = (H - total_text_height) // 2 - 15

    # 标题阴影
    for i, line in enumerate(lines):
        y = title_start_y + i * line_height
        draw.text((72, y + 3), line, font=title_font, fill=(0, 0, 0, 80))

    # 标题正文
    for i, line in enumerate(lines):
        y = title_start_y + i * line_height
        # 渐变效果：每行从左到右微渐变
        draw.text((70, y), line, font=title_font, fill=TEXT_WHITE)

    # ── 副标题 ───────────────────────────────────────────
    if subtitle:
        sub_font_size = 22
        sub_font = find_font(FONT_CANDIDATES_CN, sub_font_size)
        sub_y = title_start_y + len(lines) * line_height + 15
        draw.text((72, sub_y), subtitle, font=sub_font, fill=TEXT_DIM)

    # ── 底部品牌名 ────────────────────────────────────────
    brand_font = find_font(FONT_CANDIDATES_CN, 16)
    draw.text((72, H - 38), "Agent技术笔记", font=brand_font, fill=BRAND_COLOR)

    # 底部分隔线
    draw.line([(72, H - 44), (72 + 140, H - 44)], fill=BRAND_COLOR, width=1)

    # ── 右下角装饰 ────────────────────────────────────────
    draw_hexagon(draw, W - 35, H - 35, 20, HEX_COLOR + (50,), width=2)
    draw_node(draw, W - 35, H - 35, 2, ACCENT2)

    # ── 输出 ──────────────────────────────────────────────
    # 转为 RGB（去掉 alpha 通道）
    final = Image.new("RGB", (W, H), BG_TOP)
    final.paste(img, mask=img.split()[3])

    if output_path is None:
        # 默认输出到项目根目录的 images/ 下
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        images_dir = os.path.join(project_root, "images")
        os.makedirs(images_dir, exist_ok=True)
        safe_title = title.replace(" ", "_")[:20]
        output_path = os.path.join(images_dir, f"cover_{safe_title}.png")
    elif os.path.isdir(output_path) or output_path.endswith("/"):
        # 如果传入的是目录路径，自动在目录下生成文件名
        safe_title = title.replace(" ", "_")[:20]
        output_path = os.path.join(output_path, f"cover_{safe_title}.png")

    final.save(output_path, "PNG", quality=95)
    print(f"✅ 封面图已生成：{output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Agent技术笔记 封面图生成器")
    parser.add_argument("title", help="文章标题")
    parser.add_argument("--subtitle", "-s", help="副标题（可选）")
    parser.add_argument("--tag", "-t", help="标签/分类（可选，如「技术解析」「实战案例」）")
    parser.add_argument("--output", "-o", help="输出文件路径（可选，默认自动命名）")
    parser.add_argument("--seed", type=int, help="随机种子（相同种子=相同装饰布局）")

    args = parser.parse_args()
    generate_cover(args.title, args.subtitle, args.tag, args.output, args.seed)


if __name__ == "__main__":
    main()
