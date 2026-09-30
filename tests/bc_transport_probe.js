const M = require(process.argv[process.argv.length - 1]);
const chan = "pahiro-test-" + Date.now();
const a = new M.MeshRunner(new M.MeshNode("phone-a", {name: "Sita"}),
                           new M.BroadcastChannelTransport("phone-a", chan));
const b = new M.MeshRunner(new M.MeshNode("phone-b", {name: "Ram"}),
                           new M.BroadcastChannelTransport("phone-b", chan));
const sos = a.node.sos("buried, two of us", {lat: 27.762, lon: 85.0535, people: 2});
a.send(sos);
setTimeout(() => {
  b.pump();
  const m = b.node.store[sos.id];
  const c = new M.MeshRunner(new M.MeshNode("phone-c"),
                             new M.BroadcastChannelTransport("phone-c", chan));
  const handed = b.node.syncWith(c.node)[0];
  const ok = !!m && m.origin === "phone-a" && handed === 1 &&
             Object.keys(c.node.store).length === 1;
  console.log(JSON.stringify({ok: ok, origin: m && m.origin, handed: handed}));
  process.exit(ok ? 0 : 1);
}, 300);
