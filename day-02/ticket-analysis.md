# Day 02 — Ticket analysis

Nguồn: repo training không có backlog, nên 5 ticket dưới đây được tự viết từ dự án **auction platform**.

---

## Ticket 1: Thêm filter theo trạng thái cho `GET /me/bids`

> "User muốn lọc danh sách bid của mình theo trạng thái."

1. **Nó yêu cầu gì:** Thêm query param `status` vào `GET /me/bids` để chỉ trả về các bid có trạng thái được chọn.
2. **Chỗ nào mơ hồ:** Danh sách giá trị `status` hợp lệ là gì (active / outbid / won / lost / cancelled?); có cho chọn nhiều giá trị cùng lúc không; giá trị sai thì trả 400 hay bỏ qua filter.
3. **Bước đầu tiên:** Đọc model `Bid` và enum trạng thái hiện có, rồi viết test cho `GET /me/bids?status=won` trước khi sửa query.

**Câu hỏi làm rõ:**
- Các giá trị `status` nào client cần lọc? Có cần trạng thái suy ra (ví dụ "đang dẫn đầu") hay chỉ trạng thái lưu trong DB?
- Hỗ trợ nhiều giá trị không (`?status=won,lost` hoặc `?status=won&status=lost`)?
- Giá trị không hợp lệ: trả 400 hay bỏ qua?
- Filter có cần dùng chung với cursor pagination hiện tại không (cursor có cần mang theo filter không)?

---

## Ticket 2: Cursor pagination của `GET /me/bids` bị thiếu bid

> "Có user báo là lướt hết danh sách bid thì thiếu mấy bid, nhưng mở chi tiết auction thì vẫn thấy."

1. **Nó yêu cầu gì:** Sửa để duyệt qua tất cả các trang của `GET /me/bids` trả về đủ mọi bid của user, không thiếu bid nào.
2. **Chỗ nào mơ hồ:** Không có user_id, thời điểm hay page size cụ thể, không biết bid nào bị thiếu, và chưa rõ có bị trùng bid hay chỉ bị thiếu.
3. **Bước đầu tiên:** Lấy một user bị báo lỗi, so `SELECT count(*)` trong DB với tổng số item duyệt qua API, rồi xem `created_at` của những bid bị thiếu.

**Câu hỏi làm rõ:**
- User nào, page size (`limit`) bao nhiêu, app/web hay gọi API trực tiếp?
- Bid bị thiếu có điểm chung gì không, ví dụ đặt cùng lúc hoặc do auto-bid?
- Chỉ bị thiếu hay có cả bị trùng giữa các trang?
- Lỗi xảy ra luôn hay chỉ thỉnh thoảng? Từ khi nào?

→ Xem [bug-report.md](bug-report.md): đã reproduce và có failing test.

---

## Ticket 3: Gửi email khi user bị outbid

> "Khi có người trả giá cao hơn thì báo cho user."

1. **Nó yêu cầu gì:** Khi một bid mới vượt bid đang dẫn đầu thì gửi thông báo cho người vừa bị vượt.
2. **Chỗ nào mơ hồ:** Kênh gửi là email, push hay in-app; có gộp hoặc giới hạn số thông báo khi bị outbid liên tục không; user có tắt được không.
3. **Bước đầu tiên:** Tìm chỗ trong code xử lý `place_bid` xác định bid dẫn đầu cũ, rồi kiểm tra hệ thống đã có job queue hoặc mail service chưa.

**Câu hỏi làm rõ:**
- Kênh nào: email, push hay in-app? Có cần cả ba không?
- Nếu trong 1 phút bị outbid 10 lần thì gửi 10 email hay gộp lại?
- Có cần setting cho user opt-out không?
- Có gửi khi auction sắp kết thúc (ví dụ < 1 phút) hay có rule riêng?
- Có template/nội dung email sẵn chưa, ai duyệt?

---

## Ticket 4: Chặn đặt bid sau khi auction đã kết thúc

> "Vẫn đặt được bid khi auction đã hết giờ."

1. **Nó yêu cầu gì:** `POST /auctions/{id}/bids` phải từ chối bid khi thời điểm hiện tại đã qua `ends_at` của auction.
2. **Chỗ nào mơ hồ:** Mốc so sánh là giờ server hay giờ nhận request; mã lỗi trả về là 409 hay 422; có cơ chế anti-sniping (gia hạn thời gian) cần giữ nguyên không.
3. **Bước đầu tiên:** Viết test đặt bid với `ends_at` trong quá khứ để xác nhận lỗi, rồi đọc validation hiện tại của `place_bid`.

**Câu hỏi làm rõ:**
- So với giờ server (UTC) hay giờ trong request?
- Có rule anti-sniping (bid trong N giây cuối thì gia hạn) không?
- Mã lỗi và message mong muốn là gì?
- Bid đặt "đúng lúc" `ends_at` (bằng nhau đến mili giây) thì tính là hợp lệ hay không?
- Có cần xử lý các bid đã lọt vào sau giờ kết thúc trước đây không?

---

## Ticket 5: Trang chi tiết auction load chậm

> "Trang auction load lâu quá."

1. **Nó yêu cầu gì:** Giảm thời gian phản hồi của `GET /auctions/{id}` (và/hoặc trang chi tiết) xuống mức chấp nhận được.
2. **Chỗ nào mơ hồ:** Không có số đo hiện tại hay mục tiêu (bao nhiêu ms), không rõ chậm ở backend hay frontend, auction nào và lượng bid bao nhiêu.
3. **Bước đầu tiên:** Đo latency của `GET /auctions/{id}` với một auction có nhiều bid và bật query log để đếm số query (nghi N+1).

**Câu hỏi làm rõ:**
- "Chậm" là bao nhiêu giây? Mục tiêu là bao nhiêu (p95 < ? ms)?
- Auction cụ thể nào? Có nhiều bid không?
- Chậm ở lần load đầu hay mọi lần? Mạng/thiết bị nào?
- Bắt đầu chậm từ khi nào (sau deploy nào)?

---

## So sánh với Claude

Mình đưa 5 ticket thô (phần trích dẫn) cho Claude và nhờ chỉ ra chỗ thiếu. Những điểm Claude nêu thêm so với 3 câu của mình:

| Ticket | Claude nêu thêm |
|---|---|
| 1 | Filter có ảnh hưởng tới cursor không: nếu đổi filter giữa chừng thì cursor cũ có còn hợp lệ? |
| 2 | Có thể là thiếu do **tie trên `created_at`**, cần hỏi page size vì lỗi chỉ lộ ra khi bid cùng mili giây rơi đúng ranh giới trang. |
| 3 | Idempotency: retry job có làm gửi email trùng không. |
| 4 | Race condition: hai request đến sát `ends_at`, kiểm tra và insert phải nằm trong cùng transaction. |
| 5 | Cần phân biệt cold cache và warm cache khi đo. |

Bài học: 3 câu của mình bắt được phần "nghiệp vụ mơ hồ", còn Claude hay bắt thêm phần **edge case kỹ thuật** (tie, race, idempotency).

## Role-play: hỏi người báo lỗi (Ticket 2)

Claude đóng vai người báo lỗi (PM nhận report từ user):

> **Mình:** User nào bị, và họ xem trên app hay web?
> **Reporter:** User `42`, xem trên app mobile, tab "My bids".
>
> **Mình:** App gọi `GET /me/bids` với `limit` bao nhiêu?
> **Reporter:** Mình không chắc, dev mobile nói là 20.
>
> **Mình:** Bid bị thiếu có gì đặc biệt không, ví dụ đặt cùng lúc?
> **Reporter:** User có bật auto-bid cho mấy auction, mấy bid đó bị thiếu.
>
> **Mình:** Có bị lặp bid nào không, hay chỉ thiếu?
> **Reporter:** Chỉ thiếu, không thấy lặp.
>
> **Mình:** Lỗi xảy ra luôn hay thỉnh thoảng?
> **Reporter:** Thỉnh thoảng, refresh lại thì có khi thấy có khi không (do bid mới đẩy ranh giới trang đi).

→ Auto-bid fan-out tạo nhiều bid trong cùng mili giây, và lỗi chỉ xảy ra khi các bid đó nằm vắt qua ranh giới trang. Thông tin này dẫn thẳng tới giả thuyết H1 trong bug report.
