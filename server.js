const express = require("express");
const fs = require("fs");
const app = express();

app.use(express.json());

const DB = "keys.json";

// DB 로드
function load(){
  if(!fs.existsSync(DB)) return [];
  return JSON.parse(fs.readFileSync(DB));
}

// DB 저장
function save(data){
  fs.writeFileSync(DB, JSON.stringify(data,null,2));
}

// 랜덤 키 생성
function genKey(){
  return "MCR-" + Math.random().toString(36).substr(2,8).toUpperCase();
}

// 상태 확인
app.get("/", (req,res)=>{
  res.json({status:"MCR License Server Running"});
});


// ==========================
// 🔥 키 생성
// ==========================
app.post("/generate_key",(req,res)=>{
  const {days=30,count=1} = req.body;

  let db = load();
  let out = [];

  for(let i=0;i<count;i++){
    const key = genKey();

    db.push({
      key,
      days,
      used:false,
      expire:null
    });

    out.push(key);
  }

  save(db);
  res.json({keys:out});
});


// ==========================
// 🔥 키 목록
// ==========================
app.get("/keys",(req,res)=>{
  res.json(load());
});


// ==========================
// 🔥 키 검증 (프로그램용)
// ==========================
app.post("/verify",(req,res)=>{
  const {key} = req.body;
  let db = load();

  const item = db.find(k=>k.key===key);

  if(!item) return res.json({ok:false,msg:"키 없음"});

  // 처음 사용 시 → 기간 시작
  if(!item.used){
    item.used = true;
    item.expire = Date.now() + item.days*86400000;
    save(db);
  }

  if(Date.now() > item.expire)
    return res.json({ok:false,msg:"기간 만료"});

  res.json({ok:true,expire:item.expire});
});


// ==========================
// 🔥 키 삭제
// ==========================
app.get("/delete",(req,res)=>{
  const {key} = req.query;
  let db = load().filter(k=>k.key!==key);
  save(db);
  res.json({ok:true});
});


app.listen(process.env.PORT || 3000, ()=>{
  console.log("Server running");
});