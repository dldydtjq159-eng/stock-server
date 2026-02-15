const express = require("express");
const fs = require("fs");

const app = express();
app.use(express.json());

const DB_FILE = "keys.json";

function loadDB(){
  if(!fs.existsSync(DB_FILE)) return [];
  return JSON.parse(fs.readFileSync(DB_FILE));
}

function saveDB(data){
  fs.writeFileSync(DB_FILE, JSON.stringify(data,null,2));
}

// =====================
// 🔥 관리자 로그인
// =====================
app.post("/api/login",(req,res)=>{
  const {id,pw} = req.body;

  if(id==="admin" && pw==="1234")
    res.json({success:true});
  else
    res.json({success:false});
});

// =====================
// 🔥 키 생성
// =====================
app.post("/api/generate",(req,res)=>{
  const {days,count} = req.body;
  const db = loadDB();

  for(let i=0;i<count;i++){
    const key = Math.random().toString(36).substr(2,10).toUpperCase();

    db.push({
      key,
      days,
      used:false,
      start:null,
      expire:null,
      pc:null
    });
  }

  saveDB(db);
  res.json({ok:true});
});

// =====================
// 🔥 키 목록
// =====================
app.get("/api/list",(req,res)=>{
  res.json(loadDB());
});

// =====================
// 🔥 키 삭제
// =====================
app.get("/api/delete",(req,res)=>{
  const key=req.query.key;
  const db=loadDB().filter(k=>k.key!==key);
  saveDB(db);
  res.json({ok:true});
});

// =====================
// 🔥 고객 로그인 / 인증
// =====================
app.post("/api/use",(req,res)=>{

  const {key, pc} = req.body;
  const db = loadDB();

  const k = db.find(x=>x.key===key);

  if(!k) return res.json({ok:false,msg:"키 없음"});

  // 🔒 PC 고정
  if(k.pc && k.pc !== pc)
    return res.json({ok:false,msg:"다른 PC에서 사용중"});

  const now = Date.now();

  // ===== 최초 사용 =====
  if(!k.used){

    k.used = true;
    k.start = now;
    k.expire = now + k.days*86400000;
    k.pc = pc;

    saveDB(db);

    return res.json({
      ok:true,
      remain:k.days
    });
  }

  // ===== 이미 사용중 =====

  if(now > k.expire)
    return res.json({ok:false,msg:"기간 만료"});

  const remain = Math.ceil((k.expire-now)/86400000);

  res.json({ok:true,remain});
});

// =====================
app.listen(3000,()=>console.log("MCR Server Running"));
