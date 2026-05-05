# Reflection - Lab 19
**Tên:** Trần Đặng Quang Huy - 2A202600292
**Cohort:** _A20_
**Path da chay:** _docker_

---

## Cau hoi (<= 200 chu)

> Tren golden set 50 queries, mode nao thang o loai query nao (`exact` /
> `paraphrase` / `mixed`), va tai sao? Khi nao ban **khong** dung hybrid
> (i.e. khi nao pure BM25 hoac pure vector la lua chon dung)?

Hybrid (RRF) thang tong the (78.6%) vi ket hop lexical signal cua BM25 va semantic signal cua vector search. Theo tung nhom query: `exact` thi keyword/hybrid deu rat cao (gan 96.7%) do match tu khoa truc tiep; `mixed` thi hybrid cao nhat (100.0%) nho fusion; `paraphrase` trong bai nay semantic khong vuot keyword vi tokenization baseline con don gian (whitespace split) tren corpus tieng Viet, nen embedding chua tach nghia du manh. Khong dung hybrid khi (1) can latency va chi phi thap nhat cho exact lookup -> dung BM25; (2) query paraphrase tu do, nhieu dong nghia, it tu khoa domain -> dung vector; (3) can giai thich va debug de dang trong rule-based flow -> BM25 hop ly hon.

---

## Dieu ngac nhien nhat khi lam lab nay

Hybrid chi hon keyword vua phai (+0.8pp), khong phai luc nao cung cach biet lon. Chat luong chunking/tokenization va du lieu dau vao moi la don bay lon nhat.

---

## Bonus challenge

- [x] Da lam bonus (xem `bonus/`)
- [ ] Pair work voi: _<ten dong doi neu co>_
