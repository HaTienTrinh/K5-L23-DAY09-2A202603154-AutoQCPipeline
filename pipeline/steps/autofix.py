"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Bẫy cần nghĩ tới (có test cho từng cái)
- Một file có NHIỀU dòng lỗi: số dòng trong `issues` là số dòng GỐC. Nếu xoá từng dòng một thì số dòng lệch.
  Gom theo file, rồi ghi lại MỘT lần.
- Sau khi cắt, box có thể không còn diện tích (nằm hẳn ngoài ảnh): lúc đó xoá dòng thay vì ghi box rỗng.
- Một dòng có 2 lỗi (vd. BOX_OUT_OF_IMAGE + DUP_BOX): xoá dòng thắng, chỉ ghi 1 fix `drop_line`, không ghi thêm `clip_box`. Dòng trống ở giữa file vẫn đếm vào số dòng gốc.
- Ảnh vừa bị xoá (DUP_IMAGE_*...) mà còn issue dòng của chính nó: bỏ qua êm, không được báo lỗi/chết.
- Không động tới lỗi WARN (cảnh báo là việc của người). Không sửa file ở `data/raw/` — chỉ sửa `ds`.
- Chạy lần 2 trên dữ liệu đã sửa phải không làm gì thêm (idempotent) — NGOẠI LỆ duy nhất: `needs_label` được ghi lại mỗi lần còn lỗi `MISSING_LABEL_FILE` (vì ảnh vẫn chưa có nhãn).

- `needs_label` KHÔNG tạo file nhãn rỗng (rỗng = "ảnh nền", khác với "chưa gán"). `review_queue` sẽ đẩy ảnh này lên đầu hàng đợi cho người.

Gợi ý: `yaml.safe_load / safe_dump`.
"""
from collections import defaultdict  # noqa: F401

import yaml  # noqa: F401

from ..common import ERROR, parse_yolo_line  # noqa: F401

DROP_CODES = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}
CLIP_CODES = {"BOX_OUT_OF_IMAGE"}
REMOVE_CODES = {"DUP_IMAGE_EXACT", "DUP_IMAGE_NEAR", "LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}


def _fmt(cid, x, y, w, h):
    return f"{cid} {x:.6f} {y:.6f} {w:.6f} {h:.6f}"


def _clip(text):
    """Cắt box về [0,1]. Trả về dòng mới, hoặc None nếu box không còn diện tích (hoặc dòng không đọc được)."""
    try:
        cid, x, y, w, h = parse_yolo_line(text)
    except ValueError:
        return None
    x1, x2 = max(0.0, x - w / 2), min(1.0, x + w / 2)
    y1, y2 = max(0.0, y - h / 2), min(1.0, y + h / 2)
    if x2 <= x1 or y2 <= y1:
        return None
    return _fmt(cid, (x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1)


def _remove_image(ds, stem):
    img = ds.image_path(stem)
    before = img.name if img else "(không có ảnh)"
    if img:
        img.unlink()
    lp = ds.label_path(stem)
    if lp.exists():
        before += f" + {lp.name}"
        lp.unlink()
    return dict(image=stem, line="", action="remove_image", before=before, after="(đã xoá)")


def _rename_classes(ds, cfg):
    d = {}
    if ds.yaml_path.exists():
        d = yaml.safe_load(ds.yaml_path.read_text(encoding="utf-8")) or {}
    old = d.get("names")
    d["names"] = list(cfg["classes"])
    if "nc" in d:
        d["nc"] = len(cfg["classes"])
    ds.yaml_path.write_text(yaml.safe_dump(d, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return dict(image="data.yaml", line="", action="rename_classes", before=str(old), after=str(d["names"]))


def fix(ds, issues, cfg):
    errors = [i for i in issues if i.severity == ERROR]
    fixes = []

    # 1) Lỗi cấp ẢNH: xoá ảnh + nhãn (mỗi ảnh một lần, theo thứ tự tên).
    removed = set()
    for stem in sorted({i.image for i in errors if i.code in REMOVE_CODES}):
        fixes.append(_remove_image(ds, stem))
        removed.add(stem)

    # 2) Tên lớp trong data.yaml (một lần dù có nhiều issue BAD_CLASS_NAME).
    if any(i.code == "BAD_CLASS_NAME" for i in errors):
        fixes.append(_rename_classes(ds, cfg))

    # 3) Ảnh chưa có file nhãn: máy không bịa nhãn, chỉ ghi lại để chuyển người gán.
    for stem in sorted({i.image for i in errors if i.code == "MISSING_LABEL_FILE"} - removed):
        if not ds.label_path(stem).exists():
            fixes.append(dict(image=stem, line="", action="needs_label",
                              before="(không có file)", after="chuyển người gán"))

    # 4) Lỗi DÒNG: gom theo file -> {số dòng gốc: tập mã lỗi}, rồi ghi file lại MỘT lần.
    by_file = defaultdict(lambda: defaultdict(set))
    for i in errors:
        if i.line is not None and i.code in DROP_CODES | CLIP_CODES and i.image not in removed:
            by_file[i.image][int(i.line)].add(i.code)

    for stem in sorted(by_file):
        lp = ds.label_path(stem)
        if not lp.exists():
            continue
        raw = lp.read_text(encoding="utf-8", errors="replace").splitlines()   # giữ cả dòng trống: số dòng = số dòng gốc
        out, changed = [], False
        for no, text in enumerate(raw, 1):
            codes = by_file[stem].get(no)
            if not codes or not text.strip():
                out.append(text)
                continue
            if codes & DROP_CODES:                       # xoá dòng thắng: không ghi thêm clip_box
                fixes.append(dict(image=stem, line=no, action="drop_line", before=text, after="(xoá)"))
                changed = True
                continue
            new = _clip(text)                            # chỉ còn BOX_OUT_OF_IMAGE
            if new is None:                              # nằm hẳn ngoài ảnh: xoá thay vì ghi box rỗng
                fixes.append(dict(image=stem, line=no, action="drop_line", before=text, after="(xoá: box ngoài ảnh)"))
                changed = True
                continue
            if new != text:
                fixes.append(dict(image=stem, line=no, action="clip_box", before=text, after=new))
                changed = True
            out.append(new)
        if changed:
            lp.write_text("".join(ln + "\n" for ln in out), encoding="utf-8")

    return fixes
