# Báo cáo Day 09 — Hà Tiến Trịnh, 2A202603154

## 1. Kết luận trước
**HOLD** (mã thoát 10). **224 ảnh vào → 202 ảnh ra** `submission/export/clean_v1` (bản nháp, chưa phát hành); 22 ảnh bị loại ở cửa vào.
Sau sửa tự động và người duyệt **không còn lỗi bắt buộc** (0 ERROR trong `07_error_list_v3`), nhưng **38/202 ảnh (18,8%)** còn cảnh báo chưa người duyệt, vượt ngưỡng `warn_ratio_hold` 10%.
Lý do gốc: hàng đợi người duyệt có **125 ảnh** trong khi ngân sách chỉ **80 ảnh** (`08_summary.json`).

## 2. Lỗi và phân việc
Số liệu từ `01_intake` + `02_error_list_v1` (trước khi sửa). Mẫu số: 224 ảnh quét ở cửa vào; 202 ảnh vào QC.

**Lỗi bắt buộc (ERROR) — máy xử lý**

| Mã lỗi | Số ảnh/dòng | Ai sửa (máy/người) | Vì sao |
|---|---:|---|---|
| DUP_IMAGE_EXACT | 8 ảnh / 224 | máy (loại ở cửa vào) | trùng từng byte: giữ ảnh đầu, bỏ bản sao (md5 không thể sai) |
| LEAK_TEST | 5 ảnh / 224 | máy (loại) | trùng ảnh test/gold_val: để lại sẽ làm điểm test bị thổi phồng |
| DUP_IMAGE_NEAR | 4 ảnh / 224 | máy (loại) | trùng gần đúng (phash ≤ 12); đã mở xem cả 4 cặp đều là cùng ảnh |
| BAD_SIZE | 3 ảnh / 224 | máy (loại) | cạnh ngắn < 250 px, không dùng được để train |
| CORRUPT_IMAGE | 2 ảnh / 224 | máy (loại) | không mở được (ảnh cắt cụt chỉ lộ khi `load()`) |
| BOX_OUT_OF_IMAGE | 8 dòng / 8 ảnh | máy (`clip_box` ×8) | cắt box về [0,1] là an toàn, giữ nguyên lớp |
| DUP_BOX | 7 dòng / 7 ảnh | máy (`drop_line`) | box lặp cùng lớp IoU > 0.9: xoá bản sau, không mất thông tin |
| BAD_CLASS_ID | 6 dòng / 6 ảnh | máy (`drop_line`) | id ngoài 0..3: không đoán được lớp đúng nên xoá dòng |
| BOX_ZERO | 4 dòng / 4 ảnh | máy (`drop_line`) | box rỗng, không có vật |
| BAD_FORMAT | 3 dòng / 3 ảnh | máy (`drop_line`) | dòng không đọc được |
| BAD_CLASS_NAME | 2 lỗi / 1 file `data.yaml` | máy (`rename_classes`) | tên lớp có quy tắc cố định trong `cfg["classes"]` |
| MISSING_LABEL_FILE | 6 ảnh / 202 | **người** (`needs_label`) | máy **không bịa nhãn**; không tạo file rỗng vì rỗng nghĩa là "ảnh nền" |

Tổng cộng `03_fixes.csv` ghi **35 thay đổi**: 20 `drop_line`, 8 `clip_box`, 6 `needs_label`, 1 `rename_classes`.

**Cảnh báo (WARN) — người duyệt** (máy chỉ gắn cờ, vì model cũng có thể sai)

| Mã | Số lỗi / số ảnh (trên 202) |
|---|---|
| POSSIBLE_MISSING | 53 / 52 |
| POSSIBLE_FALSE_POS | 29 / 27 |
| POSSIBLE_LOOSE_BOX | 28 / 24 |
| POSSIBLE_WRONG_CLASS | 18 / 18 |
| EMPTY_LABEL | 12 / 12 |
| BOX_TINY | 6 / 4 |
| BOX_HUGE | 3 / 3 |
| CLASS_RARE | 4 (cấp dataset) |

**Hàng đợi `05_review_queue.csv`** xếp ảnh theo tổng `trọng số mã lỗi × (1 + conf)`:
- Đầu hàng là `img_0020` (11,52 điểm): cùng lúc có WRONG_CLASS, MISSING và một dòng đã bị máy xoá.
- Tiếp theo là **6 ảnh `NEEDS_LABEL`** (10 điểm mỗi ảnh, trọng số cao nhất): ảnh chưa có nhãn thì chỉ người gán được, và nếu bỏ sót sẽ ra Rework.
- Sau đó là các ảnh có WRONG_CLASS (trọng số 3) và MISSING / FALSE_POS (2), xếp theo conf của model.

**Với ngân sách 80 ảnh:**
- Hàng đợi có 125 ảnh, trong đó **103 ảnh có lỗi ngữ nghĩa** (`POSSIBLE_*`). Người duyệt xem được **74/103** ảnh đó.
- **29 ảnh có lỗi ngữ nghĩa và 45 ảnh trong hàng đợi không ai xem.**
- Ảnh cuối được duyệt có priority 3,343, ảnh đầu bị bỏ có 3,333. Ranh giới sát nhau như vậy cho thấy ngân sách đang cắt ngang vùng ảnh còn đáng xem.
- Box theo lớp (`class_stats.csv`): car 101, **person 574**, truck 41, bus 32. Dữ liệu lệch mạnh về person; truck và bus ít.

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
**(a) Cửa chặn thật sự chặn.** Chạy pipeline không có người duyệt:
```
python -m pipeline.run --budget 0 --work work/run_nb --reports work/rep_nb --export-dir work/exp_nb
```
- Kết luận **REWORK**, **mã thoát 20**: "còn 6 lỗi bắt buộc (MISSING_LABEL_FILE): phải sửa trước khi xuất".
  Sáu ảnh đó là img_0031, 0053, 0126, 0135, 0170, 0219; ngoài ra 112/202 ảnh (55,5%) còn cảnh báo.
- **Không xuất dataset**: log ghi "KHÔNG xuất: còn lỗi bắt buộc (Rework) — trả về bước 3"; `08_summary.json` có `"exported": null`; thư mục `work/exp_nb` không được tạo.
- So với lần chạy chính (ngân sách 80): người duyệt gán nhãn cho 6 ảnh `NEEDS_LABEL` (đứng đầu hàng đợi) → hết lỗi bắt buộc → kết luận chuyển từ Rework sang Hold.
- Điều này chứng minh máy không tự "lấp" lỗi thiếu nhãn để qua cửa.

**(b) Điểm pipeline KHÔNG bắt được**

Đối chiếu lỗi tự nhìn thấy (Bước 1, `viz_labels.py`) với `02_error_list_v1` (cấu hình đã calibrate, `conf = 0.6`):

| Ảnh | Lỗi quan sát | Loại lỗi | Pipeline có bắt được? |
|---|---|---|---|
| `img_0001` | Có người trong ảnh nhưng không được gán box | thiếu nhãn | ✅ `POSSIBLE_MISSING` person, conf 0.95 |
| `img_0005` | Vật ở góc trái bị gán nhầm thành `person` | gán nhầm vật / box không có thật | ❌ không có cờ nào (cờ MISSING conf 0.30 ở `conf = 0.25` cũng bị lọc ở 0.6) |
| `img_0020` | Gán `person` cho ảnh phản chiếu trong gương (người không có thật) | ngữ nghĩa: box sai ý nghĩa | ❌ không có `FALSE_POS` cho người trong gương: model cũng "thấy" người ở đó. Ảnh vẫn lên đầu hàng đợi nhờ lỗi khác (WRONG_CLASS truck→bus). |
| `img_0045` | Người bị gán nhầm lớp thành `car` | gán nhầm lớp | ⚠️ chỉ có `POSSIBLE_LOOSE_BOX` person (IoU 0.33), không có `WRONG_CLASS` |

Các điểm mù có bằng chứng:
1. **Lỗi ngữ nghĩa mà model lớn cũng mắc** (img_0020, người trong gương). `second_opinion` chỉ cờ khi nhãn và model *bất đồng*; khi cả hai cùng sai thì im lặng. Chỉ người mới bắt được.
2. **Box sai mà model vẫn thấy "có gì đó" ở đó** (img_0005). FALSE_POS chỉ bật khi box nhãn không khớp *bất kỳ* dự đoán nào có conf ≥ `fp_conf` 0.1. Một dự đoán yếu chồng lên là đủ để box sai qua mặt.
3. **Ảnh trùng biến đổi mạnh** (img_0084 ↔ img_0074, cùng ảnh bị cắt, phash dist 16). Không bị loại vì nâng `phash_dist` lên 16 sẽ gộp nhầm 8 cặp ảnh khác (xem §3).
4. **Ngân sách duyệt**: 29 ảnh có lỗi ngữ nghĩa nằm ngoài 80 ảnh được xem. Lỗi trên các ảnh này đi thẳng vào dataset nếu ép Release.

## 5. Train: raw vs clean (tùy chọn, chấm riêng)
**Chưa chạy.** Đã push `submission/export/clean_v1/` (kèm `manifest.json`) lên repo public và thử chạy `notebooks/day09_train_compare.ipynb` trên Colab, nhưng không hoàn thành được trong thời gian làm bài.
Vì vậy `submission/results/` để trống và **không có kết luận nào về việc `clean` tốt hơn `raw`**.

Nếu chạy lại, những gì cần kiểm (chưa có số liệu, chỉ là giả thuyết):
- `raw` chứa 5 ảnh `LEAK_TEST` trùng với tập test, nên mAP của `raw` có thể bị thổi phồng.
- `clean` vẫn còn 38 ảnh có cảnh báo chưa người duyệt.
- Test chỉ có 100 ảnh với 2 seed, nên chênh lệch rất có thể nằm trong nhiễu.

## 6. Quyết định và ghi chú AI
**(a) Quyết định cuối: HOLD.** `clean_v1` chỉ là bản nháp để thử nghiệm, **chưa phát hành**.

Khớp số liệu: 0 lỗi bắt buộc, 38/202 ảnh (18,8%) còn cảnh báo chưa duyệt ≥ 10%.

Điều kiện để đổi quyết định:
- **Thành Release:** số ảnh còn cảnh báo chưa duyệt phải ≤ 20/202 (< 10%). Tức là người duyệt cần xem thêm **ít nhất 18 ảnh** trong 45 ảnh còn lại của `05_review_queue.csv` (ưu tiên 29 ảnh có `POSSIBLE_*`), ví dụ bằng một vòng duyệt thứ hai hoặc tăng ngân sách duyệt trong guideline dự án. **Không** đạt Release bằng cách nâng `second_opinion.conf` lên 0.8: cách đó chỉ giấu cảnh báo (xem §3).
- **Thành Rework:** nếu người duyệt không gán nhãn cho 6 ảnh `NEEDS_LABEL` (đã chứng minh ở §4a), hoặc vòng duyệt sau làm phát sinh lỗi bắt buộc mới.
- **Trước khi phát hành** nên có người xem riêng các điểm mù ở §4b (img_0005, img_0020, img_0045, cặp img_0084/img_0074), vì máy không cờ chúng.

**(b) Ghi chú dùng AI** (Claude Code, trợ lý lập trình trong VS Code):
1. **Prompt chính:** "đọc repo và hướng dẫn; viết `label_format.py` / `gate.py` / `autofix.py` / `second_opinion.py` theo docstring và test có sẵn". Tôi cùng AI đọc từng test trước khi viết.
2. **Cách kiểm:**
   - `pytest` 79/79.
   - Tự thử thêm 3 ca ngoài test: dòng trống ở giữa file, một dòng dính 2 lỗi (tràn + trùng), chạy check trên `data/raw`.
   - Chạy `pipeline.run` rồi đọc `03_fixes.csv` (trước → sau) và đối chiếu với 4 ảnh tự xem bằng `viz_labels.py`.
   - Mở ảnh từng cặp bị cho là trùng trước khi chọn `phash_dist`.
3. **Một lần AI chưa đúng:** *(bạn tự điền một ca thật bạn gặp)*.
   Nếu không có, ghi trung thực: code AI qua test ngay, nhưng `second_opinion` vẫn bỏ sót lỗi ngữ nghĩa (img_0020 người trong gương, img_0005), và `check_submission.py` báo lỗi giả trên Windows với `calibrate.py` (file viết sẵn, sha1 khớp bản gốc; nguyên nhân là đường dẫn `\` khác `/`).

*(Thưởng +2, tùy chọn)* CVAT: lọc `width < 20`, ảnh/số box khớp, đối chiếu `BOX_TINY` (xem docs/CVAT_FILTER.md), 1 câu về `can_review`.
