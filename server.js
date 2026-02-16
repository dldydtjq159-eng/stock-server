const express = require("express");
const fs = require("fs");

const app = express();
app.use(express.json());

const PORT = process.env.PORT || 3000;
const DB_FILE = "db.json";

// =========================
// DB 로드/저장
// =========================
function loadDB() {
  if (!fs.existsSync(DB_FILE))
    return { users: {}, keys: {} };
  return JSON.parse(fs.readFileSync(DB_FILE));
}

function saveDB(data) {
  fs.writeFileSync(DB_FILE, JSON.stringify(data, null, 2));
}

let db = loadDB();

// =========================
// 서버 상태
// =========================
app.get("/", (req, res) => {
  res.json({ status: "MCR License Server Running" });
});

// =========================
// 관리자 로그인
// =========================
app.post("/admin_login", (req, res) => {
  const { id, pw } = req.body;

  if (id === "admin" && pw === "1234")
    return res.json({ success: true });

  res.json({ success: false });
});

// =========================
// 키 생성
// =========================
app.post("/generate_key", (req, res) => {
  const { days = 30, count = 1 } = req.body;

  let list = [];

  for (let i = 0; i < count; i++) {
    const key =
      "KEY-" +
      Math.random().toString(36)
        .substring(2, 10)
        .toUpperCase();

    db.keys[key] = {
      days,
      used: false,
      expire: 0,
      user: null
    };

    list.push(key);
  }

  saveDB(db);
  res.json({ success: true, keys: list });
});

// =========================
// 키 목록 조회
// =========================
app.get("/keys", (req, res) => {
  res.json(db.keys);
});

// =========================
// 키 삭제
// =========================
app.post("/delete_key", (req, res) => {
  const { key } = req.body;

  delete db.keys[key];
  saveDB(db);

  res.json({ success: true });
});

// =========================
// 회원가입
// =========================
app.post("/signup", (req, res) => {
  const { id, pw } = req.body;

  if (db.users[id])
    return res.json({ success: false, msg: "이미 존재" });

  db.users[id] = {
    pw,
    expire: 0,
    pc: null
  };

  saveDB(db);
  res.json({ success: true });
});

// =========================
// 로그인
// =========================
app.post("/login", (req, res) => {
  const { id, pw } = req.body;
  const user = db.users[id];

  if (!user || user.pw !== pw)
    return res.json({ success: false });

  let remain = 0;

  if (user.expire > Date.now())
    remain = Math.ceil(
      (user.expire - Date.now()) / 86400000
    );

  res.json({ success: true, remain_days: remain });
});

// =========================
// 키 사용
// =========================
app.post("/use_key", (req, res) => {
  const { id, key, pc } = req.body;

  const user = db.users[id];
  const k = db.keys[key];

  if (!user) return res.json({ success: false });
  if (!k || k.used) return res.json({ success: false });

  if (user.pc && user.pc !== pc)
    return res.json({ success: false, msg: "다른 PC" });

  user.expire = Date.now() + k.days * 86400000;
  user.pc = pc;

  k.used = true;
  k.user = id;
  k.expire = user.expire;

  saveDB(db);
  res.json({ success: true });
});

// =========================
// 프로그램 검증
// =========================
app.post("/check", (req, res) => {
  const { id, pc } = req.body;
  const user = db.users[id];

  if (!user) return res.json({ valid: false });
  if (user.pc && user.pc !== pc)
    return res.json({ valid: false });
  if (user.expire < Date.now())
    return res.json({ valid: false });

  res.json({ valid: true });
});

app.listen(PORT, () => {
  console.log("Server running on port " + PORT);
});
