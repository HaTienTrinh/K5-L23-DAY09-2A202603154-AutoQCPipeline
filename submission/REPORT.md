# Báo cáo Day 09 — <Họ và tên>, <MSHV>

> Xoá mọi `TODO(học viên)` và dòng gợi ý. Mỗi ý trả lời bằng **số lấy từ `submission/reports/`**, kèm mẫu số. Cả báo cáo ~1–2 trang.

## 1. Kết luận trước
TODO(học viên): pipeline kết luận **Release / Hold / Rework**? Bao nhiêu ảnh vào, bao nhiêu ảnh ra dataset? Lý do chính (1–3 câu).

## 2. Lỗi và phân việc
Lấy từ `02_error_list_v1` (gom theo mã lỗi). Cột "ai sửa": **máy** (autofix) hay **người** (hàng đợi); chỉ ghi những mã có mặt trong lô của bạn.

| Mã lỗi | Số ảnh/dòng | Ai sửa (máy/người) | Vì sao |
|---|---:|---|---|
| TODO(học viên) | | | |

TODO(học viên): vì sao `05_review_queue.csv` xếp ảnh đầu hàng như vậy? Với ngân sách 80 ảnh, người xem được bao nhiêu lỗi ngữ nghĩa?

## 3. Calibration (2 ngưỡng)
| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|---|---|---|---|
| `duplicates.phash_dist` | 2 | **12** | DUP_IMAGE_NEAR: 1.00 / 0.50 → 1.00 / 0.67 (EXACT giữ 1.00 / 1.00) | Lỗi này dẫn tới **xoá ảnh tự động** → ưu tiên precision. 10–14 cho kết quả giống hệt nhau trên cả calib và raw; chọn 12 ở giữa vùng ổn định: bắt cặp trùng thật xa nhất trên raw (img_0186/img_0061, dist 10) và cách 4 đơn vị so với 16, nơi bắt đầu gộp nhầm. |
| `second_opinion.conf` | 0.25 | **0.6** | MISSING: 0.50 / 1.00 → 0.57 / 1.00; WRONG_CLASS: 0.56 / 0.83 → 0.62 / 0.83; LOOSE_BOX: 0.29 / 0.40 → 0.20 / 0.20 (FALSE_POS không đổi 0.31 / 1.00 vì dùng `fp_conf` cố định) | Chỉ là **cảnh báo cho người** → ưu tiên recall. 0.6 là ngưỡng cao nhất còn giữ recall MISSING = 1.00 trên calib; trên raw cờ MISSING giảm 152 → 53, hàng đợi 143 → 125. Không chọn 0.8 (cho Release 7,9%) vì recall MISSING tụt còn 0.75 (sót 2/8): hàng đợi nhỏ vì checker bỏ sót là Release giả. Đánh đổi chấp nhận: LOOSE_BOX recall giảm 0.40 → 0.20. |

**Một chỗ calibration đánh lừa: `phash_dist = 16` đẹp nhất trên calib nhưng hỏng trên raw.**
Trên calib, 16 cho recall DUP_IMAGE_NEAR cao nhất (0.83, F1 0.91) và precision vẫn 1.00. Nhưng khi chạy trên raw và mở xem từng cặp:
- Số ảnh bị loại vì `LEAK_TEST` tăng 5 → 11. Cả 6 ca mới đều là ảnh **khác hẳn** (vd. img_0013 bàn làm việc ↔ test_087 sân bóng chày; img_0021 người đi bộ ↔ test_048 xe buýt).
- `DUP_IMAGE_NEAR` thêm 2 cặp giả (img_0011 tennis ↔ img_0008 trượt tuyết; img_0177 lướt sóng ↔ img_0113 người ngồi bàn).
- Ngay trên calib, dist 16 cũng sinh 1 `LEAK_TEST` giả (calib không có ca rò rỉ nào), nhưng bảng sweep **không hiện** vì chỉ chấm EXACT/NEAR.
- Ở dist 20 còn tệ hơn: 105 ảnh raw bị coi là rò rỉ test.

Nghĩa là precision 1.00 trên calib không bảo đảm precision trên raw. Ngoài ra calib chỉ có 6 ca NEAR, nên mỗi ca thêm hoặc bớt làm recall nhảy ~17%.
Điểm mù đã biết: img_0084 ↔ img_0074 là cùng ảnh bị cắt mạnh (dist 16), không ngưỡng an toàn nào bắt được.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được
TODO(học viên): (a) chứng minh gate chặn đúng: chạy `python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb` (không có người duyệt nên ảnh thiếu file nhãn còn nguyên), chỉ ra kết luận **Rework**, mã thoát 20 và việc **không xuất** dataset. (Đừng sửa tay `work/run/ds`: pipeline dựng lại thư mục này từ raw mỗi lần chạy.) (b) ≥ 2 điểm mù có bằng chứng (box lỏng nhẹ, nhầm lớp mà model lớn cũng nhầm, ảnh trùng biến đổi mạnh…).

**Lỗi tự nhìn thấy khi xem `viz_labels.py` (Bước 1, trước khi chạy pipeline):**

| Ảnh | Lỗi quan sát | Loại lỗi | Pipeline có bắt được? |
|---|---|---|---|
| `img_0001` | Có người trong ảnh nhưng không được gán box | thiếu nhãn | TODO: đối chiếu `POSSIBLE_MISSING` trong `02_error_list_v1` |
| `img_0005` | Vật ở góc trái bị gán nhầm thành `person` | gán nhầm vật / box không có thật | TODO: đối chiếu `POSSIBLE_FALSE_POS` / `POSSIBLE_WRONG_CLASS` |
| `img_0020` | Gán `person` cho ảnh phản chiếu trong gương (người không có thật) | ngữ nghĩa: box sai ý nghĩa | TODO: model lớn có thể cũng thấy "người" trong gương → điểm mù? |
| `img_0045` | Người bị gán nhầm lớp thành `car` | gán nhầm lớp | TODO: đối chiếu `POSSIBLE_WRONG_CLASS` |

## 5. Train: raw vs clean (tùy chọn, chấm riêng)
Chưa train: ghi "chưa chạy" và lý do, rồi bỏ qua phần còn lại của mục này. Nếu đã train: dán bảng từ `submission/results/comparison.md` (model, epoch, seed, số ảnh train mỗi biến thể).

TODO(học viên): chênh mAP50 (clean − raw) so với **độ lệch chuẩn giữa các seed**; kết luận **trung thực** (nằm trong nhiễu thì nói là chưa kết luận được); ≥ 2 giả thuyết giải thích (ảnh trùng/rò rỉ test trong `raw`, nhãn máy còn lại trong `clean`, test chỉ 100 ảnh…) và cách kiểm.

## 6. Quyết định và ghi chú AI
TODO(học viên): (a) quyết định cuối; nếu Hold/Rework cần làm gì để thành Release? (b) Dùng AI viết code? Ghi 3 dòng: prompt chính, cách bạn kiểm code AI, 1 lần AI sai. Không dùng: ghi "không dùng".

*(Thưởng +2, tùy chọn)* CVAT: lọc `width < 20`, ảnh/số box khớp, đối chiếu `BOX_TINY` (xem docs/CVAT_FILTER.md), 1 câu về `can_review`.
