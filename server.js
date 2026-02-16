const express = require("express");
const sqlite3 = require("sqlite3").verbose();

const app = express();
app.use(express.json());

const PORT = process.env.PORT || 3000;

// ===== DB =====
const db = new sqlite3.Database("mcr.db");

db.serialize(() => {
  db.run(`CREATE TABLE IF NOT EXISTS users(
    id TEXT PRIMARY KEY,
    pw TEXT,
    expire INTEGER,
    pc TEXT
  )`);

  db.run(`CREATE TABLE IF NOT EXISTS keys(
    key TEXT PRIMARY KEY,
    days INTEGER,
    used INTEGER
  )`);
});

// =================
// 서버 확인
// =================
app.get("/", (req, res) => {
  res.json({ status: "MCR License Server Running" });
});

// =================
// 회원가입
// =================
app.post("/signup", (req, res) => {
  const { id, pw } = req.body;

  db.run(
    "INSERT INTO users VALUES (?, ?, 0, NULL)",
    [id, pw],
    err => {
      if (err) return res.json({ success: false });
      res.json({ success: true });
    }
  );
});

// =================
// 로그인
// =================
app.post("/login", (req, res) => {
  const { id, pw } = req.body;

  db.get(
    "SELECT * FROM users WHERE id=? AND pw=?",
    [id, pw],
    (err, row) => {
      if (!row) return res.json({ success: false });

      let remain = 0;
      if (row.expire > Date.now())
        remain = Math.ceil((row.expire - Date.now()) / 86400000);

      res.json({ success: true, remain_days: remain });
    }
  );
});

// =================
// 키 생성 (관리자)
// =================
app.post("/generate_key", (req, res) => {
  const { days = 30 } = req.body;

  const key =
    "KEY-" +
    Math.random().toString(36).substring(2, 10).toUpperCase();

  db.run(
    "INSERT INTO keys VALUES (?, ?, 0)",
    [key, days],
    () => res.json({ success: true, key })
  );
});

// =================
// 키 목록 조회
// =================
app.get("/keys", (req, res) => {
  db.all("SELECT * FROM keys", [], (err, rows) => {
    res.json(rows);
  });
});

// =================
// 키 사용
// =================
app.post("/use_key", (req, res) => {
  const { id, key, pc } = req.body;

  db.get("SELECT * FROM keys WHERE key=?", [key], (err, k) => {
    if (!k || k.used) return res.json({ success: false });

    db.get("SELECT * FROM users WHERE id=?", [id], (err, u) => {
      if (!u) return res.json({ success: false });

      if (u.pc && u.pc !== pc)
        return res.json({ success: false, msg: "다른 PC" });

      const expire = Date.now() + k.days * 86400000;

      db.run(
        "UPDATE users SET expire=?, pc=? WHERE id=?",
        [expire, pc, id]
      );

      db.run("UPDATE keys SET used=1 WHERE key=?", [key]);

      res.json({ success: true });
    });
  });
});

// =================
// 상태 확인 (프로그램용)
// =================
app.post("/check", (req, res) => {
  const { id, pc } = req.body;

  db.get("SELECT * FROM users WHERE id=?", [id], (err, u) => {
    if (!u) return res.json({ valid: false });
    if (u.pc && u.pc !== pc) return res.json({ valid: false });
    if (u.expire < Date.now()) return res.json({ valid: false });

    res.json({ valid: true });
  });
});

app.listen(PORT, () =>
  console.log("Server running on port " + PORT)
);
