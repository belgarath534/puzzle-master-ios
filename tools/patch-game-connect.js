// Makes @osmanraifgunes/capacitor-game-connect build with Swift Package
// Manager. The plugin ships an Objective-C CAP_PLUGIN file next to its Swift
// code, and SwiftPM refuses targets that mix languages ("contains mixed
// language source files"). Capacitor 8 plugins register in Swift instead
// (CAPBridgedPlugin), so this swaps the .m/.h for the same declaration in
// Swift. Runs after every npm install; safe to run again.
const fs = require('fs');
const path = require('path');

const dir = path.join(__dirname, '..', 'node_modules', '@osmanraifgunes', 'capacitor-game-connect', 'ios', 'Plugin');
const swift = path.join(dir, 'CapacitorGameConnectPlugin.swift');
if (!fs.existsSync(swift)) process.exit(0);

for (const f of ['CapacitorGameConnectPlugin.m', 'CapacitorGameConnectPlugin.h']) {
  const p = path.join(dir, f);
  if (fs.existsSync(p)) fs.unlinkSync(p);
}

let src = fs.readFileSync(swift, 'utf8');
if (src.includes('CAPBridgedPlugin')) process.exit(0);

const methods = ['signIn', 'showLeaderboard', 'showAchievements', 'submitScore', 'unlockAchievement',
  'incrementAchievementProgress', 'getUserTotalScore', 'getGameCenterCredential', 'getGooglePlayCredential'];
const decl = 'public class CapacitorGameConnectPlugin: CAPPlugin {';
if (!src.includes(decl)) { console.error('patch-game-connect: plugin source changed, not patched'); process.exit(1); }
src = src.replace(decl, [
  'public class CapacitorGameConnectPlugin: CAPPlugin, CAPBridgedPlugin {',
  '    public let identifier = "CapacitorGameConnectPlugin"',
  '    public let jsName = "CapacitorGameConnect"',
  '    public let pluginMethods: [CAPPluginMethod] = [',
  ...methods.map(m => `        CAPPluginMethod(name: "${m}", returnType: CAPPluginReturnPromise),`),
  '    ]',
].join('\n'));
fs.writeFileSync(swift, src);
console.log('patch-game-connect: plugin registers in Swift now');
