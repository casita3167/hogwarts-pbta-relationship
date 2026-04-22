// src/firebase.js
import { initializeApp } from "firebase/app";

// 這些就是你截圖中的資訊
const firebaseConfig = {
  apiKey: "AIzaSyDV06_5tTecR4q9EZUQ32IBy91KsFxSCHA",
  authDomain: "hogwarts-pbta-relationsh-31ba9.firebaseapp.com",
  projectId: "hogwarts-pbta-relationsh-31ba9",
  storageBucket: "hogwarts-pbta-relationsh-31ba9.firebasestorage.app",
  messagingSenderId: "361459597273",
  appId: "1:361459597273:web:66c7174720052f826323c8"
};

// 初始化 Firebase
const app = initializeApp(firebaseConfig);
export default app;