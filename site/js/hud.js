// The pixel-style HUD. Everything shown is built with textContent and createElement, so no string from live.json or
// anywhere else can inject markup.
import { fmtDec, fmtRa } from './ephemeris.js';
import { cardinal } from './target.js';
import { drawEyepiece } from './eyepiece.js';

const $ = (id) => document.getElementById(id);
const timeFormat = new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
const dateFormat = new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Kolkata', weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' });

export class Hud {
  constructor() {
    this.el = {
      root: $('hud'), time: $('hud-time'), date: $('hud-date'), strip: $('compass-strip'), heading: $('compass-heading'),
      sky: $('hud-sky'), weather: $('hud-weather'), readout: $('readout'), readoutBody: $('readout-body'), hint: $('hud-hint'),
      help: $('hud-help'),
    };
    this.lastSky = '';
    this.lastClock = '';
    this.lastHeading = -1;
    this.buildCompass();
  }

  buildCompass() {
    const strip = this.el.strip;
    const PX = 4;                                       // pixels per degree
    strip.style.setProperty('--px', `${PX}px`);
    for (let turn = 0; turn < 3; turn++) {
      for (let deg = 0; deg < 360; deg += 15) {
        const mark = document.createElement('span');
        const named = deg % 45 === 0;
        mark.className = named ? 'mark major' : 'mark';
        mark.style.setProperty('--x', `${(turn * 360 + deg) * PX}px`);
        mark.textContent = named ? ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'][deg / 45] : '';
        strip.appendChild(mark);
      }
    }
    this.px = PX;
  }

  setHeading(deg) {
    const h = Math.round(deg) % 360;
    if (h === this.lastHeading) return;
    this.lastHeading = h;
    const half = this.el.strip.parentElement.clientWidth / 2 || 160;
    this.el.strip.style.setProperty('--shift', `${half - (360 + deg) * this.px}px`);
    this.el.heading.textContent = `${String(h).padStart(3, '0')}° ${cardinal(deg)}`;
  }

  setClock(date) {
    const text = `${timeFormat.format(date)} IST`;
    if (text !== this.lastClock) {
      this.lastClock = text;
      this.el.time.textContent = text;
      this.el.date.textContent = `Mumbai · ${dateFormat.format(date)}`;
    }
  }

  setSky(lines, weatherText) {
    const key = lines.join('|') + weatherText;
    if (key === this.lastSky) return;
    this.lastSky = key;
    const list = this.el.sky;
    list.textContent = '';
    for (const line of lines) {
      const li = document.createElement('li');
      li.textContent = line;
      list.appendChild(li);
    }
    this.el.weather.textContent = weatherText;
  }

  showTelescope(target) {
    $('eyepiece-title').textContent = target.name;
    const status = target.daylight ? 'Daylight — return after dusk for tonight’s target.' : target.altitude <= 0 ? 'Below the horizon — the mount will continue tracking. Return when it rises.' : 'Tracking tonight’s object in the real Mumbai sky';
    if ($('eyepiece-status').textContent !== status) $('eyepiece-status').textContent = status;
    $('eyepiece-caption').textContent = 'Pixel-art illustration · not a live camera image';
    $('eyepiece-canvas').setAttribute('aria-label', `${target.name} pixel-art illustration`);
    drawEyepiece($('eyepiece-canvas'), target);
    const body = this.el.readoutBody;
    body.textContent = '';
    const rows = [
      ['Telescope target', target.name],
      ['RA (J2000)', fmtRa(target.raHours)],
      ['Dec (J2000)', fmtDec(target.decDeg)],
      ['Altitude', `${target.altitude.toFixed(1)}°`],
      ['Azimuth', `${target.azimuth.toFixed(1)}° ${cardinal(target.azimuth)}`],
      ['Magnitude', target.magnitude.toFixed(1)],
    ];
    for (const [label, value] of rows) {
      const dt = document.createElement('dt');
      dt.textContent = label;
      const dd = document.createElement('dd');
      dd.textContent = value;
      body.append(dt, dd);
    }
    this.el.readout.hidden = false;
  }

  hideTelescope() {
    this.el.readout.hidden = true;
  }

  get readoutOpen() {
    return !this.el.readout.hidden;
  }

  setHint(text) {
    this.el.hint.textContent = text;
  }
}
