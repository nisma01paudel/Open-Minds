/* Pahiro mesh, in JavaScript.
 *
 * This is the SAME protocol as src/pahiro/mesh/ — same frame format, same TTL rule, same
 * dedupe, same store-and-forward, same "chat is evicted before an SOS" rule. It is not a
 * summary of it and not a simplified version for the browser: a message composed on a
 * phone must be relayed correctly by a gateway written in Python, and vice versa.
 *
 * That duplication is a hazard, so it is checked rather than trusted:
 * scripts/check_mesh_parity.py runs one scenario through both implementations and compares
 * the outcome. Two implementations of one protocol in two languages WILL drift, and each
 * will pass its own tests while the two disagree.
 *
 * Transports:
 *   BroadcastChannelTransport - real, working, same-origin, across tabs on one device.
 *                               This is how the demo runs two "phones" on one laptop.
 *   BleTransport              - the interface a phone implements. Declared, not faked.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) { module.exports = factory(); }
  else { root.PahiroMesh = factory(); }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var WIRE_VERSION = 1;
  var DEFAULT_TTL = 7;
  var MAX_BODY = 480;
  var PRIORITY = { sos: 0, beacon: 1, status: 2, ack: 3, chat: 4 };

  function nowIso() {
    // second resolution, matching the Python: the wire format carries seconds, so a model
    // that kept milliseconds would not equal itself after a round trip.
    return new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
  }

  function newId() {
    var s = "", i;
    for (i = 0; i < 16; i++) { s += "0123456789abcdef"[Math.floor(Math.random() * 16)]; }
    return s;
  }

  /* ---- the frame ------------------------------------------------------------------- */

  function MeshMessage(f) {
    f = f || {};
    if (!(f.kind in PRIORITY)) {
      throw new Error("unknown message kind " + JSON.stringify(f.kind) +
                      "; expected one of " + Object.keys(PRIORITY).sort().join(", "));
    }
    this.kind = f.kind;
    this.body = f.body == null ? "" : String(f.body);
    if (this.body.length > MAX_BODY) {
      // Truncation beats a dropped SOS, and the reader is told they are not seeing all of it.
      this.body = this.body.slice(0, MAX_BODY - 14).replace(/\s+$/, "") + " [truncated]";
    }
    this.origin = f.origin;
    this.origin_name = f.origin_name || "";
    this.id = f.id || newId();
    this.created_at = f.created_at || nowIso();
    this.ttl = f.ttl == null ? DEFAULT_TTL : f.ttl;
    this.hops = f.hops || 0;
    this.path = f.path ? f.path.slice() : [];
    this.reply_to = f.reply_to || null;
    this.lat = f.lat == null ? null : f.lat;
    this.lon = f.lon == null ? null : f.lon;
    this.accuracy_m = f.accuracy_m == null ? null : f.accuracy_m;
    this.people = f.people == null ? null : f.people;
    this.battery = f.battery == null ? null : f.battery;
  }

  MeshMessage.prototype.priority = function () { return PRIORITY[this.kind]; };
  MeshMessage.prototype.isSos = function () { return this.kind === "sos"; };
  MeshMessage.prototype.hasPosition = function () { return this.lat !== null && this.lon !== null; };
  MeshMessage.prototype.alive = function () { return this.ttl > 0; };

  MeshMessage.prototype.relay = function (via) {
    if (this.ttl <= 0) { throw new Error("cannot relay a message with ttl <= 0"); }
    var c = new MeshMessage(this);
    c.ttl = this.ttl - 1;
    c.hops = this.hops + 1;
    c.path = this.path.concat([via]);
    return c;
  };

  MeshMessage.prototype.toDict = function () {
    var d = { v: WIRE_VERSION, id: this.id, k: this.kind, b: this.body, o: this.origin,
              n: this.origin_name, t: this.created_at, ttl: this.ttl, h: this.hops };
    if (this.path.length) { d.p = this.path; }
    if (this.reply_to) { d.r = this.reply_to; }
    if (this.lat !== null) { d.y = Math.round(this.lat * 1e6) / 1e6; }
    if (this.lon !== null) { d.x = Math.round(this.lon * 1e6) / 1e6; }
    if (this.accuracy_m !== null) { d.a = Math.round(this.accuracy_m * 10) / 10; }
    if (this.people !== null) { d.pp = this.people; }
    if (this.battery !== null) { d.bat = this.battery; }
    return d;
  };

  MeshMessage.fromDict = function (d) {
    if (!d || typeof d !== "object") { throw new Error("mesh frame must be an object"); }
    if ((d.v == null ? WIRE_VERSION : d.v) !== WIRE_VERSION) {
      throw new Error("unsupported wire version " + d.v);
    }
    ["id", "k", "o"].forEach(function (k) {
      if (d[k] == null) { throw new Error("mesh frame missing required field '" + k + "'"); }
    });
    return new MeshMessage({
      id: d.id, kind: d.k, body: d.b, origin: d.o, origin_name: d.n,
      created_at: d.t, ttl: d.ttl, hops: d.h, path: d.p, reply_to: d.r,
      lat: d.y, lon: d.x, accuracy_m: d.a, people: d.pp, battery: d.bat
    });
  };

  MeshMessage.prototype.toBytes = function () { return JSON.stringify(this.toDict()); };

  MeshMessage.fromBytes = function (raw) {
    // A frame off the radio must never be guessed at: a relay that invents a message is
    // worse than one that drops it.
    if (typeof raw !== "string") {
      if (raw && typeof raw.byteLength === "number") {
        raw = new TextDecoder().decode(raw);
      } else { throw new Error("not a mesh frame"); }
    }
    var d;
    try { d = JSON.parse(raw); } catch (e) { throw new Error("not a mesh frame: " + e.message); }
    return MeshMessage.fromDict(d);
  };

  /* ---- the node -------------------------------------------------------------------- */

  function MeshNode(deviceId, opts) {
    opts = opts || {};
    this.device_id = deviceId;
    this.name = opts.name || deviceId;
    this.ttl = opts.ttl == null ? DEFAULT_TTL : opts.ttl;
    this.capacity = opts.capacity == null ? 200 : opts.capacity;
    this.seen = {};
    this.store = {};
    this.inbox = [];
    this.stats = { sent: 0, received: 0, duplicates: 0, expired: 0, evicted: 0, relayed: 0 };
  }

  MeshNode.prototype.compose = function (kind, body, fields) {
    var f = fields || {};
    f.kind = kind; f.body = body; f.origin = this.device_id;
    if (!f.origin_name) { f.origin_name = this.name; }
    if (f.ttl == null) { f.ttl = this.ttl; }
    var m = new MeshMessage(f);
    this._remember(m);
    this.inbox.push(m);
    return m;
  };

  MeshNode.prototype.sos = function (body, fields) { return this.compose("sos", body, fields); };
  MeshNode.prototype.chat = function (body, replyTo) {
    return this.compose("chat", body, { reply_to: replyTo || null });
  };

  MeshNode.prototype.receive = function (msg) {
    if (this.seen[msg.id]) { this.stats.duplicates++; return false; }
    this.stats.received++;
    if (!msg.alive()) { this.stats.expired++; return false; }
    if (msg.origin !== this.device_id) { this.inbox.push(msg); }
    this._remember(msg);
    return true;
  };

  MeshNode.prototype.relayable = function (exclude) {
    var skip = {}, self = this;
    (exclude || []).forEach(function (id) { skip[id] = true; });
    var out = Object.keys(this.store).map(function (k) { return self.store[k]; })
      .filter(function (m) { return m.alive() && !skip[m.id]; });
    // urgent first, then newest: when two people pass each other the SOS goes and the chat
    // may never go at all.
    out.sort(function (a, b) {
      return (a.priority() - b.priority()) || (a.created_at < b.created_at ? 1 : -1);
    });
    return out;
  };

  MeshNode.prototype._remember = function (msg) {
    this.seen[msg.id] = true;
    this.store[msg.id] = msg;
    if (Object.keys(this.store).length > this.capacity) { this._evict(); }
  };

  MeshNode.prototype._evict = function () {
    // Chat before SOS, oldest first. Never simply the oldest: a day-old SOS is still a
    // person, and a fresh joke is not.
    var self = this, worst = null;
    Object.keys(this.store).forEach(function (k) {
      var m = self.store[k];
      if (!worst || m.priority() > worst.priority() ||
          (m.priority() === worst.priority() && m.created_at < worst.created_at)) { worst = m; }
    });
    if (worst) { delete this.store[worst.id]; this.stats.evicted++; }
  };

  MeshNode.prototype.syncWith = function (peer, maxMessages) {
    var cap = maxMessages == null ? 50 : maxMessages;
    var self = this, ours = Object.keys(this.store), theirs = Object.keys(peer.store);
    var sent = 0, taken = 0;

    this.relayable(theirs).slice(0, cap).forEach(function (m) {
      try { peer.receive(m.relay(self.device_id)); }
      catch (e) { self.stats.expired++; return; }
      self.stats.relayed++; self.stats.sent++; sent++;
    });
    peer.relayable(ours).slice(0, cap).forEach(function (m) {
      try { if (self.receive(m.relay(peer.device_id))) { taken++; peer.stats.relayed++; peer.stats.sent++; } }
      catch (e) { peer.stats.expired++; }
    });
    return [sent, taken];
  };

  MeshNode.prototype.distress = function () {
    var self = this, byOrigin = {};
    Object.keys(this.store).forEach(function (k) {
      var m = self.store[k];
      if (!m.isSos()) { return; }
      var prev = byOrigin[m.origin];
      if (!prev || m.created_at > prev.created_at) { byOrigin[m.origin] = m; }
    });
    return Object.keys(byOrigin).map(function (k) { return byOrigin[k]; })
      .sort(function (a, b) {
        return (a.hasPosition() ? 0 : 1) - (b.hasPosition() ? 0 : 1) ||
               (a.created_at < b.created_at ? 1 : -1);
      });
  };

  MeshNode.prototype.transcript = function (kind) {
    return this.inbox.filter(function (m) { return !kind || m.kind === kind; })
      .sort(function (a, b) { return a.created_at < b.created_at ? -1 : 1; });
  };

  /* ---- radios ---------------------------------------------------------------------- */

  function LoopbackRadio() { this.attached = {}; this.log = []; }
  LoopbackRadio.prototype.attach = function (id) { this.attached[id] = []; return this; };
  LoopbackRadio.prototype.detach = function (id) { delete this.attached[id]; };
  LoopbackRadio.prototype.broadcast = function (msg) {
    var self = this;
    Object.keys(this.attached).forEach(function (id) {
      if (id === msg.origin) { return; }
      self.attached[id].push(msg);
      self.log.push([msg.origin, id, msg]);
    });
  };
  LoopbackRadio.prototype.poll = function (id) {
    var q = this.attached[id] || (this.attached[id] = []);
    var out = q.slice(); q.length = 0; return out;
  };

  /* Cross-tab transport. Real, and it works today: two tabs on one machine behave exactly
     like two phones in radio range. It is NOT Bluetooth, and the UI says so - a demo that
     quietly swaps the radio for something easier is how you end up believing your own
     demo. On a phone the same node is driven by the BLE transport below. */
  function BroadcastChannelTransport(deviceId, channelName) {
    var self = this;
    this.device_id = deviceId;
    this.inbox = [];
    if (typeof BroadcastChannel === "undefined") { this.channel = null; return; }
    this.channel = new BroadcastChannel(channelName || "pahiro-mesh");
    this.channel.onmessage = function (ev) {
      try { self.inbox.push(MeshMessage.fromBytes(ev.data)); } catch (e) { /* ignore junk */ }
    };
  }
  BroadcastChannelTransport.prototype.broadcast = function (msg) {
    if (this.channel) { this.channel.postMessage(msg.toBytes()); }
  };
  // Takes the asking device's id for interface parity with the shared-medium radio; a
  // per-device transport ignores it.
  BroadcastChannelTransport.prototype.poll = function (deviceId) {   // eslint-disable-line no-unused-vars
    var out = this.inbox.slice(); this.inbox.length = 0; return out;
  };
  BroadcastChannelTransport.prototype.close = function () {
    if (this.channel) { this.channel.close(); }
  };

  /* The phone's radio. Declared, not implemented - there is no pretend Bluetooth stack
     here. Web Bluetooth is central-role only: this can HEAR an advertising device, but a
     browser cannot make the handset advertise in the background. */
  function BleTransport(deviceId) { this.device_id = deviceId; this.inbox = []; }
  BleTransport.MESH_SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e";
  BleTransport.MESH_CHARACTERISTIC_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e";
  BleTransport.prototype.broadcast = function () {
    throw new Error("implement with Web Bluetooth (GATT write) or a native BLE " +
                    "advertiser; see docs/MESH.md");
  };
  BleTransport.prototype.poll = function (deviceId) { return this.inbox.slice(); };
  BleTransport.prototype.advertise = function () {
    throw new Error("requires a native advertiser - a browser cannot advertise");
  };
  BleTransport.prototype.scan = function () {
    throw new Error("requires a native scanner with RSSI");
  };

  function MeshRunner(node, radio) {
    this.node = node; this.radio = radio;
    // `attach` belongs to the in-memory medium, which has to know who is listening. A real
    // radio does not, and the Transport contract promises only broadcast/poll - so calling
    // it unconditionally crashed the runner on every transport that honoured the contract.
    if (typeof radio.attach === "function") { radio.attach(node.device_id); }
  }
  MeshRunner.prototype.send = function (msg) { this.radio.broadcast(msg); };
  MeshRunner.prototype.pump = function () {
    var self = this, got = 0;
    this.radio.poll(this.node.device_id).forEach(function (m) {
      if (self.node.receive(m)) { got++; }
    });
    return got;
  };
  MeshRunner.prototype.meet = function (peer, rounds) {
    var n = rounds == null ? 3 : rounds, h = 0, t = 0, r;
    for (var i = 0; i < n; i++) {
      this.pump(); peer.pump();
      r = this.node.syncWith(peer.node); h += r[0]; t += r[1];
      if (r[0] === 0 && r[1] === 0) { break; }
    }
    return [h, t];
  };

  return {
    WIRE_VERSION: WIRE_VERSION, DEFAULT_TTL: DEFAULT_TTL, MAX_BODY: MAX_BODY,
    PRIORITY: PRIORITY,
    MeshMessage: MeshMessage, MeshNode: MeshNode,
    LoopbackRadio: LoopbackRadio, BroadcastChannelTransport: BroadcastChannelTransport,
    BleTransport: BleTransport, MeshRunner: MeshRunner
  };
}));
