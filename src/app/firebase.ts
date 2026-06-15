// Import the functions you need from the SDKs you need
import { initializeApp } from "firebase/app";
import { getAnalytics } from "firebase/analytics";
import { getAuth } from "firebase/auth";
import { getFirestore } from "firebase/firestore";

// Your web app's Firebase configuration
// For Firebase JS SDK v7.20.0 and later, measurementId is optional
const firebaseConfig = {
  apiKey: "AIzaSyAsljVre6iFAfKyzKiLEtRkMN1ukkwi3wc",
  authDomain: "modulo-c1980.firebaseapp.com",
  projectId: "modulo-c1980",
  storageBucket: "modulo-c1980.firebasestorage.app",
  messagingSenderId: "936365011803",
  appId: "1:936365011803:web:36ba17e54fbb541d59207e",
  measurementId: "G-BHERW4XHX1"
};

// Initialize Firebase
export const firebaseApp = initializeApp(firebaseConfig);
export const analytics = getAnalytics(firebaseApp);
export const auth = getAuth(firebaseApp);
export const db = getFirestore(firebaseApp);
