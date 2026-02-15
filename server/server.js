const express = require("express");
const crypto = require("crypto");
const app = express();

app.use(express.json());

const PORT = process.env.PORT || 3000;

// ===== 임시 DB (실전은 DB 연결 가능) =====
let users = {};
let keys = {};

// =======================
// 서버 상태
// =======================
app.get("/", (req, res) => {
  res.json({ status: "MCR License Server Running 🔥" });
});

// =======================
// 회원가입
// =======================
app.post("/signup", (req, res) => {
  const { id, pw } = req.body;

  if (!id || !pw)
    return res.json({ success: false, msg: "입력 오류" });

  if (users[id])
    return res.json({ success: false, msg: "이미 존재" });

  users[id] = {
    pw,
    expire: null,
    pc: null
  };

  res.json({ success: true });
});

// =======================
// 로그인
// =======================
app.post("/login", (req, res) => {
  const { id, pw } = req.body;

  const user = users[id];
  if (!user || user.pw !== pw)
    return res.json({ success: false });

  let remain = 0;

  if (user.expire) {
    const diff = user.expire - Date.now();
    remain = Math.ceil(diff / 86400000);
    if (remain < 0) remain = 0;
  }

  res.json({ success: true, remain_days: remain });
});

// =======================
// 키 생성 (관리자)
// =======================
app.post("/generate_key", (req, res) => {
  const { days = 30, count = 1 } = req.body;

  let list = [];

  for (let i = 0; i < count; i++) {
    const key =
      "MCR-" +
      crypto.randomBytes(4).toString("hex").toUpperCase();

    keys[key] = {
      days,
      used: false
    };

    list.push(key);
  }

  res.json({ success: true, keys: list });
});

// =======================
// 키 사용 (고객)
// =======================
app.post("/use_key", (req, res) => {
  const { id, key, pc } = req.body;

  const user = users[id];
  const k = keys[key];

  if (!user)
    return res.json({ success: false, msg: "회원 없음" });

  if (!k)
    return res.json({ success: false, msg: "키 없음" });

  if (k.used)
    return res.json({ success: false, msg: "이미 사용됨" });

  // PC 제한
  if (user.pc && user.pc !== pc)
    return res.json({ success: false, msg: "다른 PC 사용중" });

  const expire = Date.now() + k.days * 86400000;

  user.expire = expire;
  user.pc = pc;

  k.used = true;

  res.json({ success: true });
});

// =======================
// 키 목록 조회
// =======================
app.get("/keys", (req, res) => {
  res.json(keys);
});

app.listen(PORT, () => {
  console.log("Server running on port " + PORT);
});
