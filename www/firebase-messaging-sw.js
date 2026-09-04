importScripts('https://www.gstatic.com/firebasejs/10.7.1/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.7.1/firebase-messaging-compat.js');

firebase.initializeApp({
  apiKey: "AIzaSyAcSiqzT4yRseFGwK1iP_c0MAfc1or7A8o",
  authDomain: "puzzle-master-b457c.firebaseapp.com",
  projectId: "puzzle-master-b457c",
  storageBucket: "puzzle-master-b457c.firebasestorage.app",
  messagingSenderId: "925977595706",
  appId: "1:925977595706:web:d30e14e58064dd0d700a03"
});

const messaging = firebase.messaging();

messaging.onBackgroundMessage(function(payload) {
  const title = payload.notification.title || "Puzzle Master";
  const options = {
    body: payload.notification.body || "You have a new notification!",
    icon: '/icon-192.png'
  };
  self.registration.showNotification(title, options);
});
