# -*- coding: utf-8 -*-
"""生成 installer/icon.ico(多尺寸)+ 预览图。

图标源:**玩家指定的照片**(默认 C:\\Users\\bgyLe\\Pictures\\星愿-弟弟.png)。
处理链(每步都有理由):
  1. 按 alpha 通道**裁到主体**(原图四周有大量透明留白,不裁的话缩小后角色很小);
  2. 补成正方形并留 ~7% 边距(不变形 —— 只补透明边,不拉伸);
  3. 透明区**填白底**(玩家要求:图是透明的,给它白底);
  4. 四角**圆角**(半径 = 边长 20%);
  5. 导出 ico 多尺寸 + 两张预览(256px 大图、小尺寸放大对照)。
照片不存在、或这台机器没装 Pillow 时:

  · 找不到照片 → 保留现有 icon.ico,只打印一行中文提示(不让构建失败);
  · 没有 Pillow  → 打印一行中文提示后 exit 0(构建脚本用的是一个没装依赖的
    Python,以前这里会刷一段 ModuleNotFoundError 的噪声)。
"""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "icon.ico"
SIZES = [256, 128, 64, 48, 32, 16]
PHOTO = Path(os.environ.get("LYRA_ICON_PHOTO")
             or r"C:\Users\bgyLe\Pictures\星愿-弟弟.png")
MARGIN = 0.07          # 主体四周留白(占边长)
RADIUS = 0.20          # 圆角半径(占边长)


def build_from_photo(src: Path):
    from PIL import Image, ImageDraw

    im = Image.open(src)
    im = im.convert("RGBA")
    # ① 裁到主体(alpha 的包围盒)
    box = im.split()[3].getbbox()
    if box:
        im = im.crop(box)
    # ② 补成正方形(补透明,不拉伸)
    w, h = im.size
    side = max(w, h)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(im, ((side - w) // 2, (side - h) // 2), im)
    im = canvas
    # ③ 留边距 + 填白底
    inner = int(side * (1 - MARGIN * 2))
    im = im.resize((inner, inner), Image.LANCZOS)
    full = Image.new("RGBA", (side, side), (255, 255, 255, 255))
    full.paste(im, ((side - inner) // 2, (side - inner) // 2), im)
    # ④ 圆角
    mask = Image.new("L", (side, side), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, side - 1, side - 1],
                                           radius=int(side * RADIUS), fill=255)
    out = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    out.paste(full, (0, 0), mask)
    return out


def main() -> None:
    try:
        from PIL import Image          # noqa: F401
    except Exception:
        print("  (跳过图标生成:这个 Python 没有 Pillow,沿用现有 icon.ico)")
        return
    from PIL import Image

    if not PHOTO.is_file():
        print("  (找不到图标源图 %s,沿用现有 icon.ico)" % PHOTO)
        return
    try:
        master = build_from_photo(PHOTO)
    except Exception as e:
        print("  (图标生成失败:%s,沿用现有 icon.ico)" % e)
        return

    frames = [master.resize((s, s), Image.LANCZOS) for s in SIZES]
    frames[0].save(OUT, format="ICO", sizes=[(s, s) for s in SIZES])
    print("  图标已生成:%s  尺寸 %s  (源图 %s)" % (OUT.name, SIZES, PHOTO.name))
    frames[0].save(OUT.with_name("icon-preview-256.png"))
    small = [master.resize((s, s), Image.LANCZOS).resize((s * 6, s * 6), Image.NEAREST)
             for s in (16, 32, 48, 64)]
    W = sum(x.width for x in small) + 5 * (len(small) + 1)
    H = max(x.height for x in small) + 10
    sheet = Image.new("RGB", (W, H), (24, 26, 34))
    x = 5
    for im in small:
        sheet.paste(im, (x, (H - im.height) // 2), im)
        x += im.width + 5
    sheet.save(OUT.with_name("icon-preview-small.png"))
    print("  预览:icon-preview-256.png / icon-preview-small.png")


if __name__ == "__main__":
    main()
