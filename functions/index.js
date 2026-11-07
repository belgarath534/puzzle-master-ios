// Firebase Cloud Functions for Puzzle Master.
//
// cleanupDeletedUser runs whenever a Firebase Auth account is deleted (from
// the in-app Delete Account button or the Firebase console) and removes
// everything that player left in Firestore, including leaderboard scores
// from past weeks that the app itself can't reach.
const functions = require("firebase-functions/v1");
const admin = require("firebase-admin");

admin.initializeApp();

exports.cleanupDeletedUser = functions.auth.user().onDelete(async (user) => {
  const db = admin.firestore();
  const uid = user.uid;
  const writer = db.bulkWriter();
  let count = 0;

  // Cloud save
  writer.delete(db.doc(`users/${uid}`)); count++;

  // Weekly leaderboards: leaderboard/{week}__global/entries/{uid} and
  // leaderboard/{week}__cat{N}/entries/{uid}. listDocuments() also returns
  // parent docs that only exist as a path, which is how these are stored.
  const boards = await db.collection("leaderboard").listDocuments();
  for (const board of boards) {
    writer.delete(board.collection("entries").doc(uid)); count++;
  }

  // Blitz leaderboard: blitzLeaderboard/{week}_{uid}, each with a uid field
  const blitz = await db.collection("blitzLeaderboard").where("uid", "==", uid).get();
  blitz.forEach((d) => { writer.delete(d.ref); count++; });

  await writer.close();
  functions.logger.info(`Cleaned up ${count} document paths for deleted user ${uid}`);
});
