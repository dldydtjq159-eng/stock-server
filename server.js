const express = require("express");
const app = express();

app.use(express.json());

const PORT = process.env.PORT || 3000;

// ===== DB =====
let users = {};
let keys = {};

// =====================
// 서버 확인
// =====================
app.get("/", (req, res) => {
  res.json({ status: "MCR License Server Running" });
});

// =====================
// 회원가입
// =====================
app.post("/signup", (req, res) => {
  const { id, pw } = req.body;

  if (users[id])
    return res.json({ success: false, msg: "이미 존재" });

  users[id] = {
    pw: pw,
    expire: null,
    pc: null
  };

  res.json({ success: true });
});

// =====================
// 로그인
// =====================
app.post("/login", (req, res) => {
  const { id, pw } = req.body;
  const user = users[id];

  if (!user || user.pw !== pw)
    return res.json({ success: false });

  let remain = 0;
  let need_key = true;

  if (user.expire) {
    const diff = user.expire - Date.now();
    remain = Math.ceil(diff / 86400000);

    if (remain > 0) need_key = false;
    else remain = 0;
  }

  res.json({
    success: true,
    remain_days: remain,
    need_key: need_key
  });
});

// =====================
// 키 생성 (관리자)
// =====================
app.post("/generate_key", (req, res) => {
  const { days = 30, count = 1 } = req.body;

  let list = [];

  for (let i = 0; i < count; i++) {
    const key = "MCR-" + Math.random().toString(36)
      .substring(2, 10)
      .toUpperCase();

    keys[key] = {
      days: days,
      used: false
    };

    list.push(key);
  }

  res.json({ success: true, keys: list });
});

// =====================
// 코드 등록
// =====================
app.post("/use_key", (req, res) => {
  const { id, key, pc } = req.body;

  const user = users[id];
  const k = keys[key];

  if (!user) return res.json({ success: false, msg: "회원 없음" });
  if (!k) return res.json({ success: false, msg: "키 없음" });
  if (k.used) return res.json({ success: false, msg: "이미 사용됨" });

  // PC 제한
  if (user.pc && user.pc !== pc)
    return res.json({ success: false, msg: "다른 PC" });

  const expire = Date.now() + k.days * 86400000;

  user.expire = expire;
  user.pc = pc;

  k.used = true;

  res.json({ success: true });
});

app.listen(PORT, () => {
  console.log("MCR Server running on port " + PORT);
});
