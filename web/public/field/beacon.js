/* The Bluetooth-advertisement beacon codec, in JavaScript.
 *
 * This is the SAME wire format as src/pahiro/mesh/beacon.py - same 20 bytes, same field
 * offsets, same FNV-1a truncation, same CRC-8/ATM, same relay rule. It is not a summary of it
 * and not a simplified version for the browser.
 *
 * Two implementations of one format in two languages WILL drift, and each will pass its own
 * tests while the two disagree - at which point a frame emitted by a Python district server's
 * relay and one heard by a JavaScript phone are different messages, or worse, the same message
 * that neither side recognises as a duplicate. So the agreement is checked rather than
 * trusted: scripts/check_beacon_parity.py runs one frame through both and compares the bytes.
 *
 * WHAT THIS CAN AND CANNOT DO
 * ---------------------------
 * decode() is the half a browser can complete. Web Bluetooth has no advertiser role - a page
 * can scan and can connect as a central, but it cannot put bytes on the air - so encode() here
 * exists for the tests and for a native bridge to call, not because a web page can transmit.
 * `canAdvertise` records that honestly rather than letting a caller assume otherwise.
 *
 * SCANNING IS REAL AND IS WIRED UP
 * --------------------------------
 * navigator.bluetooth.requestLEScan({ acceptAllAdvertisements: true }) delivers
 * `advertisementreceived` events carrying manufacturerData, with no connection and no pairing.
 * `watchAdvertisements` below uses it, so a phone with this page open collects beacons from
 * handsets that have never heard of us.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) { module.exports = factory(); }
  else { root.PahiroBeacon = factory(); }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var WIRE_VERSION = 1;
  var MAX_AD_BYTES = 24;   // payload we control inside a 31-byte legacy advertisement
  var ENCODED_BYTES = 20;

  var KIND_SOS = 0, KIND_BEACON = 1, KIND_STATUS = 2;
  var KIND_NAMES = { 0: "sos", 1: "beacon", 2: "status" };
  var KIND_VALUES = { sos: 0, beacon: 1, status: 2 };

  var SEVERITIES = ["info", "concern", "urgent", "critical"];

  var MAX_TTL = 7, MAX_HOPS = 7, MAX_PEOPLE = 15;
  var AGE_BUCKET_SECONDS = 300;

  var FLAG_HAS_POSITION = 0x01, FLAG_LOW_BATTERY = 0x02;
  var POS_SCALE = 100000;

  /* FNV-1a 32-bit, folded to 16. See the Python docstring: blake2s was the first choice and
   * had to go, because the browser cannot compute it and a truncation that differs across the
   * language boundary is a dedupe failure. Math.imul gives the wrapping 32-bit multiply. */
  function truncate16(value) {
    var bytes = utf8(String(value));
    var h = 0x811C9DC5;
    for (var i = 0; i < bytes.length; i++) {
      h = Math.imul(h ^ bytes[i], 0x01000193) >>> 0;
    }
    return (h ^ (h >>> 16)) & 0xFFFF;
  }

  function utf8(s) {
    var out = [];
    for (var i = 0; i < s.length; i++) {
      var c = s.charCodeAt(i);
      if (c < 0x80) { out.push(c); }
      else if (c < 0x800) {
        out.push(0xC0 | (c >> 6), 0x80 | (c & 0x3F));
      } else if (c >= 0xD800 && c <= 0xDBFF && i + 1 < s.length) {
        var c2 = s.charCodeAt(i + 1);
        var cp = 0x10000 + ((c - 0xD800) << 10) + (c2 - 0xDC00);
        out.push(0xF0 | (cp >> 18), 0x80 | ((cp >> 12) & 0x3F),
                 0x80 | ((cp >> 6) & 0x3F), 0x80 | (cp & 0x3F));
        i++;
      } else {
        out.push(0xE0 | (c >> 12), 0x80 | ((c >> 6) & 0x3F), 0x80 | (c & 0x3F));
      }
    }
    return out;
  }

  /* CRC-8/ATM, polynomial 0x07, init 0x00 - byte for byte the Python implementation. */
  function crc8(data) {
    var crc = 0x00;
    for (var i = 0; i < data.length; i++) {
      crc ^= data[i];
      for (var b = 0; b < 8; b++) {
        crc = (crc & 0x80) ? (((crc << 1) ^ 0x07) & 0xFF) : ((crc << 1) & 0xFF);
      }
    }
    return crc;
  }

  function bucketOf(date) {
    return (Math.floor(date.getTime() / 1000 / AGE_BUCKET_SECONDS)) >>> 0;
  }

  function unpackBucket(b) {
    return new Date(b * AGE_BUCKET_SECONDS * 1000);
  }

  function pushU16(out, v) { out.push((v >>> 8) & 0xFF, v & 0xFF); }
  function pushI32(out, v) {
    out.push((v >>> 24) & 0xFF, (v >>> 16) & 0xFF, (v >>> 8) & 0xFF, v & 0xFF);
  }
  function pushU32(out, v) {
    out.push((v >>> 24) & 0xFF, (v >>> 16) & 0xFF, (v >>> 8) & 0xFF, v & 0xFF);
  }
  function u16(data, o) { return (data[o] << 8) | data[o + 1]; }
  function u32(data, o) {
    return ((data[o] * 0x1000000) + ((data[o + 1] << 16) | (data[o + 2] << 8) | data[o + 3])) >>> 0;
  }
  function i32(data, o) {
    var v = (data[o] << 24) | (data[o + 1] << 16) | (data[o + 2] << 8) | data[o + 3];
    return v;
  }

  function BeaconError(message) { this.message = message; this.name = "BeaconError"; }
  BeaconError.prototype = Object.create(Error.prototype);

  /* Build a frame from raw 16-bit identifiers. A relay holds only the truncated bits, so this
   * is the function relay() uses - it must not need the strings those bits came from. */
  function pack(dev16, msg16, opts) {
    opts = opts || {};
    var kind = opts.kind === undefined ? "sos" : opts.kind;
    var severity = opts.severity === undefined ? "urgent" : opts.severity;
    var ttl = opts.ttl === undefined ? MAX_TTL : opts.ttl;
    var hops = opts.hops === undefined ? 0 : opts.hops;
    var people = opts.people === undefined ? 0 : opts.people;
    var lat = opts.lat === undefined ? null : opts.lat;
    var lon = opts.lon === undefined ? null : opts.lon;
    var lowBattery = !!opts.lowBattery;
    var when = opts.when || new Date();

    if (!(kind in KIND_VALUES)) throw new BeaconError("unknown kind " + kind);
    if (SEVERITIES.indexOf(severity) < 0) throw new BeaconError("unknown severity " + severity);
    if (ttl < 0 || ttl > MAX_TTL) throw new BeaconError("ttl " + ttl + " outside 0.." + MAX_TTL);
    if (hops < 0 || hops > MAX_HOPS) throw new BeaconError("hops outside 0.." + MAX_HOPS);
    if (people < 0 || people > MAX_PEOPLE) throw new BeaconError("people outside 0.." + MAX_PEOPLE);
    if ((lat === null) !== (lon === null)) {
      throw new BeaconError("latitude and longitude must be given together or not at all");
    }

    var flags = 0;
    if (lat !== null) flags |= FLAG_HAS_POSITION;
    if (lowBattery) flags |= FLAG_LOW_BATTERY;

    var out = [];
    out.push((WIRE_VERSION << 5) | (KIND_VALUES[kind] << 2) | flags);
    pushU16(out, dev16 & 0xFFFF);
    pushU16(out, msg16 & 0xFFFF);
    out.push(((ttl & 0x07) << 5) | ((hops & 0x07) << 2) | SEVERITIES.indexOf(severity));
    out.push((people & 0x0F) << 4);
    if (lat === null) {
      for (var z = 0; z < 8; z++) out.push(0);
    } else {
      if (lat < -90 || lat > 90) throw new BeaconError("latitude out of range");
      if (lon < -180 || lon > 180) throw new BeaconError("longitude out of range");
      pushI32(out, Math.round(lat * POS_SCALE));
      pushI32(out, Math.round(lon * POS_SCALE));
    }
    pushU32(out, bucketOf(when));

    if (out.length !== ENCODED_BYTES - 1) {
      throw new BeaconError("layout and encoder have drifted apart: " + out.length);
    }
    out.push(crc8(out));
    return out;
  }

  function encode(deviceId, msgId, opts) {
    return pack(truncate16(deviceId), truncate16(msgId), opts);
  }

  /* Returns null for anything that is not a valid beacon. Never throws: this runs on every
   * advertisement a scanner hears, and a phone in a market hears hundreds a minute from
   * earbuds and watches. A decoder that threw would make the scanner unusable, and one that
   * guessed would turn a pair of earbuds into a landslide victim. */
  function decode(payload) {
    if (!payload) return null;
    var data = payload;
    if (typeof data === "string") {
      data = data.split("").map(function (c) { return c.charCodeAt(0) & 0xFF; });
    }
    data = Array.prototype.slice.call(data);
    if (data.length !== ENCODED_BYTES) return null;
    if (crc8(data.slice(0, ENCODED_BYTES - 1)) !== data[ENCODED_BYTES - 1]) return null;

    var header = data[0];
    if ((header >> 5) !== WIRE_VERSION) return null;
    var kind = KIND_NAMES[(header >> 2) & 0x07];
    if (kind === undefined) return null;
    var flags = header & 0x03;

    var dev16 = u16(data, 1), msg16 = u16(data, 3);
    var timing = data[5];
    var ttl = (timing >> 5) & 0x07;
    var hops = (timing >> 2) & 0x07;
    var severity = SEVERITIES[timing & 0x03];
    var people = (data[6] >> 4) & 0x0F;

    var lat = null, lon = null;
    if (flags & FLAG_HAS_POSITION) {
      lat = i32(data, 7) / POS_SCALE;
      lon = i32(data, 11) / POS_SCALE;
    }
    var created = unpackBucket(u32(data, 15));

    return {
      dev16: dev16,
      msg_id16: msg16,
      kind: kind,
      ttl: ttl,
      hops: hops,
      severity: severity,
      people: people,
      lat: lat,
      lon: lon,
      created: created,
      lowBattery: !!(flags & FLAG_LOW_BATTERY),
      hasPosition: function () { return lat !== null && lon !== null; },
      peopleText: function () {
        if (people === 0) return "unknown number of people";
        if (people >= MAX_PEOPLE) return MAX_PEOPLE + "+ people";
        return people + (people === 1 ? " person" : " people");
      },
      origin: function () { return "dev-" + hex4(dev16); },
      messageId: function () { return "beacon-" + hex4(msg16); },
      ageSeconds: function (now) {
        return ((now || new Date()).getTime() - created.getTime()) / 1000;
      },
      isStale: function (maxAgeSeconds, now) {
        if (maxAgeSeconds === undefined) maxAgeSeconds = 6 * 3600;
        var age = this.ageSeconds(now);
        return age < 0 || age > maxAgeSeconds;
      }
    };
  }

  function hex4(n) { return ("000" + n.toString(16)).slice(-4); }

  /* Decode, spend one hop, re-encode. Returns null when invalid or out of hops, which is the
   * signal to stop rebroadcasting. Every field except ttl and hops is preserved byte for byte:
   * a relay that "improved" the coordinates would be inventing a rescue location it never
   * measured, and one that changed the ids would defeat dedupe across paths of different
   * length. */
  function relay(payload) {
    var b = decode(payload);
    if (!b || b.ttl <= 0) return null;
    return pack(b.dev16, b.msg_id16, {
      kind: b.kind, lat: b.lat, lon: b.lon, ttl: b.ttl - 1,
      hops: Math.min(b.hops + 1, MAX_HOPS), severity: b.severity, people: b.people,
      lowBattery: b.lowBattery, when: b.created
    });
  }

  /* True only where the platform can actually transmit. A browser cannot, and saying so here
   * keeps a caller from building a product on a capability the platform does not have. */
  var canAdvertise = false;

  function canScan() {
    return typeof navigator !== "undefined" && navigator.bluetooth
        && typeof navigator.bluetooth.requestLEScan === "function";
  }

  /* Collect beacons from advertisements the OS is already hearing. No pairing, no connection,
   * and nothing required of the phone that emitted them - which is the entire point: the
   * trapped handset has never heard of this page. */
  function watchAdvertisements(onBeacon, opts) {
    opts = opts || {};
    if (!canScan()) return Promise.reject(new Error("requestLEScan is unavailable"));
    var companyId = opts.companyId === undefined ? null : opts.companyId;
    return navigator.bluetooth.requestLEScan({ acceptAllAdvertisements: true })
      .then(function (scan) {
        var listener = function (event) {
          var payload = null;
          if (event.manufacturerData && event.manufacturerData.size) {
            event.manufacturerData.forEach(function (view, id) {
              if (companyId !== null && id !== companyId) return;
              payload = new Uint8Array(view.buffer.slice(view.byteOffset,
                                                          view.byteOffset + view.byteLength));
            });
          }
          if (!payload) return;
          var b = decode(payload);
          if (b) onBeacon(b, event.rssi, event.device ? event.device.id : null);
        };
        navigator.bluetooth.addEventListener("advertisementreceived", listener);
        scan.stopListener = function () {
          navigator.bluetooth.removeEventListener("advertisementreceived", listener);
          try { scan.stop(); } catch (e) { /* already stopped */ }
        };
        return scan;
      });
  }

  return {
    WIRE_VERSION: WIRE_VERSION,
    MAX_AD_BYTES: MAX_AD_BYTES,
    ENCODED_BYTES: ENCODED_BYTES,
    MAX_TTL: MAX_TTL,
    MAX_HOPS: MAX_HOPS,
    MAX_PEOPLE: MAX_PEOPLE,
    AGE_BUCKET_SECONDS: AGE_BUCKET_SECONDS,
    KIND_SOS: KIND_SOS,
    KIND_BEACON: KIND_BEACON,
    KIND_STATUS: KIND_STATUS,
    SEVERITIES: SEVERITIES,
    truncate16: truncate16,
    crc8: crc8,
    pack: pack,
    encode: encode,
    decode: decode,
    relay: relay,
    canScan: canScan,
    canAdvertise: canAdvertise,
    watchAdvertisements: watchAdvertisements
  };
}));
