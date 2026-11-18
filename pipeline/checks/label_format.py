"""CHECK 2 — Dòng nhãn YOLO: sai định dạng, ID lớp lạ, box tràn ảnh, box rỗng, box lặp.   (Script 2 trong slide)   ★★

Test:  pytest tests/test_label_format.py -q

Mỗi dòng nhãn: `id cx cy w h` (5 số, toạ độ 0–1). Trả về list[Issue]; `Issue.line` = số dòng (đếm từ 1).

| code             | severity | khi nào                                                                  |
|------------------|----------|--------------------------------------------------------------------------|
| BAD_FORMAT       | ERROR    | không đúng 5 cột số (dùng `parse_yolo_line`, bắt `ValueError`)           |
| BAD_CLASS_ID     | ERROR    | id lớp ngoài 0..len(ds.classes)-1                                        |
| BOX_ZERO         | ERROR    | w <= 0 hoặc h <= 0                                                       |
| BOX_OUT_OF_IMAGE | ERROR    | mép box vượt [0,1] quá `cfg["label_format"]["overflow_tol"]`; extra={"overflow": mức tràn} |
| DUP_BOX          | ERROR    | cùng lớp với một dòng TRƯỚC ĐÓ và IoU > `dup_box_iou`; báo ở dòng SAU    |
| BOX_TINY         | WARN     | cạnh ngắn của box (px) < `min_box_px`  (cần `ds.image_size(stem)`)       |
| BOX_HUGE         | WARN     | w*h > `max_box_frac`                                                     |

Gợi ý
- Mép trái = x - w/2, mép phải = x + w/2 (xem câu hỏi "dòng YOLO nào lỗi?" trong slide).
- Một dòng hỏng (BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO) thì `continue`, đừng kiểm tiếp hình học của dòng đó.
- Dòng thiếu cột làm script của slide dừng giữa chừng: đây là lý do phải `try/except`.
- `iou_xywh(a, b)` có sẵn trong common.py.
- Ngưỡng nằm trong `cfg["label_format"]` — đừng viết cứng số vào code.
"""
from ..common import ERROR, WARN, Issue, iou_xywh, parse_yolo_line  # noqa: F401

NAME = "label_format"


def run(ds, cfg):
    c = cfg["label_format"]
    tol = c["overflow_tol"]
    min_px = c["min_box_px"]
    max_frac = c["max_box_frac"]
    dup_iou = c["dup_box_iou"]
    n_classes = len(ds.classes)

    issues = []
    for lf in ds.label_files():
        stem = lf.stem
        size = ds.image_size(stem) if ds.image_path(stem) else None   # None: không có ảnh / ảnh hỏng
        kept = []                                                      # (id, cx, cy, w, h) các box đã gặp

        for no, ln in ds.read_label_lines(stem) or []:
            # 1. Định dạng: phải đúng 5 cột số
            try:
                cid, x, y, w, h = parse_yolo_line(ln)
            except ValueError as e:
                issues.append(Issue(NAME, ERROR, "BAD_FORMAT", stem, f"dòng hỏng: {e}", line=no))
                continue

            # 2. ID lớp
            if not 0 <= cid < n_classes:
                issues.append(Issue(NAME, ERROR, "BAD_CLASS_ID", stem,
                                    f"id lớp {cid} ngoài 0..{n_classes - 1}", line=no, extra={"id": cid}))
                continue

            # 3. Box rỗng
            if w <= 0 or h <= 0:
                issues.append(Issue(NAME, ERROR, "BOX_ZERO", stem, f"box rỗng: w={w}, h={h}", line=no))
                continue

            # 4. Tràn ảnh: mức tràn lớn nhất trên 4 mép (không continue: vẫn kiểm tiếp)
            overflow = max(0 - (x - w / 2), (x + w / 2) - 1, 0 - (y - h / 2), (y + h / 2) - 1)
            if overflow > tol:
                issues.append(Issue(NAME, ERROR, "BOX_OUT_OF_IMAGE", stem,
                                    f"box tràn ảnh {overflow:.4f} > {tol}", line=no,
                                    extra={"overflow": round(overflow, 6)}))

            # 5. Box lặp: cùng lớp với một box TRƯỚC ĐÓ và IoU cao
            box = (x, y, w, h)
            dup = next((k for k in kept if k[0] == cid and iou_xywh(k[1:], box) > dup_iou), None)
            if dup is not None:
                iou = iou_xywh(dup[1:], box)
                issues.append(Issue(NAME, ERROR, "DUP_BOX", stem,
                                    f"box lặp (cùng lớp {cid}, IoU {iou:.3f})", line=no, extra={"iou": round(iou, 4)}))

            # 6. Box quá nhỏ (theo px, cạnh ngắn)
            if size:
                W, H = size
                short = min(w * W, h * H)
                if short < min_px:
                    issues.append(Issue(NAME, WARN, "BOX_TINY", stem,
                                        f"cạnh ngắn {short:.1f}px < {min_px}px", line=no, extra={"short_px": round(short, 2)}))

            # 7. Box quá lớn (tỉ lệ diện tích)
            if w * h > max_frac:
                issues.append(Issue(NAME, WARN, "BOX_HUGE", stem,
                                    f"box chiếm {w * h:.2f} diện tích ảnh > {max_frac}", line=no,
                                    extra={"frac": round(w * h, 4)}))

            kept.append((cid, x, y, w, h))
    return issues
