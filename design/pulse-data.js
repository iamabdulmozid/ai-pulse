// Karbar Pulse demo dataset. Today = Thu 15 Oct 2026. All totals reconcile: 412 open POs, 1,912,400 pcs, USD 18.6M FOB; USD 2.4M at risk; 3 factories = 70% of risk.
export const TODAY = 'Thu 15 Oct 2026';

export const FACTORIES = [
  { id: 'F01', name: 'Ananta Knitwear', loc: 'Gazipur', m: { 3: 0, 5: 48, 7: 124, 12: 86, 14: 0 }, load: 112, otd: 71, aql: 91, comp: 100, exposure: 820000, openPOs: 31, openQty: 168400, reported: 'reported', at: '09:12', status: 'critical' },
  { id: 'F02', name: 'Meghna Knitwear', loc: 'Narayanganj', m: { 3: 12, 5: 40, 7: 96, 12: 112, 14: 24 }, load: 104, otd: 78, aql: 94, comp: 96, exposure: 510000, openPOs: 27, openQty: 142800, reported: 'reported', at: '08:51', status: 'risk' },
  { id: 'F03', name: 'Padma Woollens', loc: 'Savar', m: { 3: 20, 5: 64, 7: 60, 12: 30, 14: 0 }, load: 98, otd: 82, aql: 96, comp: 92, exposure: 350000, openPOs: 22, openQty: 118200, reported: 'late', at: '11:40', status: 'risk' },
  { id: 'F04', name: 'Jamuna Knit Composite', loc: 'Ashulia', m: { 3: 0, 5: 36, 7: 80, 12: 140, 14: 48 }, load: 91, otd: 88, aql: 97, comp: 100, exposure: 190000, openPOs: 26, openQty: 131600, reported: 'reported', at: '08:20', status: 'watch' },
  { id: 'F05', name: 'Surma Sweaters', loc: 'Gazipur', m: { 3: 8, 5: 52, 7: 72, 12: 44, 14: 0 }, load: 94, otd: 84, aql: 95, comp: 88, exposure: 140000, openPOs: 19, openQty: 92400, reported: 'reported', at: '09:05', status: 'watch' },
  { id: 'F06', name: 'Shapla Sweaters', loc: 'Gazipur', m: { 3: 16, 5: 60, 7: 48, 12: 24, 14: 0 }, load: 86, otd: 91, aql: 98, comp: 100, exposure: 96000, openPOs: 24, openQty: 108600, reported: 'reported', at: '08:44', status: 'ok' },
  { id: 'F07', name: 'Karnaphuli Sweaters', loc: 'Chattogram', m: { 3: 0, 5: 24, 7: 56, 12: 96, 14: 40 }, load: 83, otd: 90, aql: 96, comp: 96, exposure: 72000, openPOs: 21, openQty: 96200, reported: 'reported', at: '09:30', status: 'ok' },
  { id: 'F08', name: 'Sundarban Knits', loc: 'Gazipur', m: { 3: 10, 5: 44, 7: 64, 12: 52, 14: 0 }, load: 79, otd: 93, aql: 97, comp: 100, exposure: 54000, openPOs: 18, openQty: 84000, reported: 'reported', at: '08:58', status: 'ok' },
  { id: 'F09', name: 'Bhairab Knitting', loc: 'Narayanganj', m: { 3: 0, 5: 32, 7: 48, 12: 72, 14: 16 }, load: 88, otd: 87, aql: 93, comp: 92, exposure: 48000, openPOs: 17, openQty: 78600, reported: 'reported', at: '09:21', status: 'watch' },
  { id: 'F10', name: 'Dhaleshwari Woollens', loc: 'Savar', m: { 3: 24, 5: 56, 7: 40, 12: 0, 14: 0 }, load: 72, otd: 95, aql: 98, comp: 100, exposure: 22000, openPOs: 16, openQty: 71200, reported: 'reported', at: '08:36', status: 'ok' },
  { id: 'F11', name: 'Teesta Knitwear', loc: 'Ashulia', m: { 3: 0, 5: 28, 7: 60, 12: 80, 14: 32 }, load: 90, otd: 86, aql: 95, comp: 96, exposure: 36000, openPOs: 19, openQty: 86400, reported: 'reported', at: '09:48', status: 'watch' },
  { id: 'F12', name: 'Kushiara Knits', loc: 'Chattogram', m: { 3: 6, 5: 40, 7: 52, 12: 36, 14: 0 }, load: 76, otd: 92, aql: 97, comp: 100, exposure: 18000, openPOs: 15, openQty: 68200, reported: 'reported', at: '08:15', status: 'ok' },
  { id: 'F13', name: 'Gomti Knitwear', loc: 'Narayanganj', m: { 3: 0, 5: 36, 7: 56, 12: 64, 14: 12 }, load: 81, otd: 89, aql: 96, comp: 92, exposure: 14000, openPOs: 16, openQty: 72800, reported: 'reported', at: '09:02', status: 'ok' },
  { id: 'F14', name: 'Rupsha Sweaters', loc: 'Savar', m: { 3: 14, 5: 48, 7: 44, 12: 20, 14: 0 }, load: 74, otd: 94, aql: 98, comp: 100, exposure: 8000, openPOs: 14, openQty: 62400, reported: 'reported', at: '08:27', status: 'ok' },
  { id: 'F15', name: 'Halda Knit', loc: 'Chattogram', m: { 3: 0, 5: 24, 7: 40, 12: 60, 14: 20 }, load: 85, otd: 85, aql: 94, comp: 76, exposure: 0, openPOs: 14, openQty: 61800, reported: 'missing', at: null, status: 'noupdate' },
  { id: 'F16', name: 'Buriganga Woollens', loc: 'Ashulia', m: { 3: 18, 5: 52, 7: 36, 12: 0, 14: 0 }, load: 70, otd: 93, aql: 97, comp: 96, exposure: 6000, openPOs: 13, openQty: 58600, reported: 'reported', at: '08:49', status: 'ok' },
  { id: 'F17', name: 'Madhumati Knitwear', loc: 'Gazipur', m: { 3: 0, 5: 32, 7: 64, 12: 56, 14: 0 }, load: 82, otd: 90, aql: 96, comp: 100, exposure: 4000, openPOs: 15, openQty: 66200, reported: 'reported', at: '09:15', status: 'ok' },
  { id: 'F18', name: 'Turag Sweaters', loc: 'Savar', m: { 3: 12, 5: 40, 7: 48, 12: 28, 14: 0 }, load: 77, otd: 92, aql: 97, comp: 100, exposure: 2000, openPOs: 13, openQty: 56800, reported: 'reported', at: '08:33', status: 'ok' },
  { id: 'F19', name: 'Bangshi Knits', loc: 'Gazipur', m: { 3: 0, 5: 28, 7: 56, 12: 48, 14: 16 }, load: 80, otd: 91, aql: 95, comp: 96, exposure: 4000, openPOs: 14, openQty: 60400, reported: 'reported', at: '09:38', status: 'ok' },
  { id: 'F20', name: 'Atrai Knitwear', loc: 'Narayanganj', m: { 3: 8, 5: 36, 7: 44, 12: 40, 14: 0 }, load: 78, otd: 88, aql: 94, comp: 80, exposure: 0, openPOs: 13, openQty: 54200, reported: 'missing', at: null, status: 'noupdate' },
  { id: 'F21', name: 'Mahananda Woollens', loc: 'Ashulia', m: { 3: 16, 5: 44, 7: 32, 12: 0, 14: 0 }, load: 68, otd: 90, aql: 96, comp: 72, exposure: 0, openPOs: 12, openQty: 46800, reported: 'missing', at: null, status: 'noupdate' },
  { id: 'F22', name: 'Feni Knit Composite', loc: 'Chattogram', m: { 3: 0, 5: 20, 7: 36, 12: 52, 14: 24 }, load: 84, otd: 86, aql: 93, comp: 84, exposure: 0, openPOs: 13, openQty: 55800, reported: 'missing', at: null, status: 'noupdate' },
];

export const POS = [
  { id: 'PO-26-1187', style: 'KW-7G-0412', desc: 'Lambswool cardigan, shawl collar', dept: 'Women', season: 'AW26', factory: 'F01', gauge: '7GG', yarn: 'Lambswool 100%', qty: 9600, fob: 24.8, exf: '29 Oct', exfDays: 14, ship: 'Sea · Chattogram', status: 'critical', risk: 92, slip: 9, prob: 18, driver: 'Linking 1,400 pcs/day vs 2,100 needed', merch: 'Nusrat J.', colours: 3, sizes: 'XS–XL' },
  { id: 'PO-26-1203', style: 'KM-12G-0877', desc: 'Merino crew-neck pullover', dept: 'Men', season: 'AW26', factory: 'F02', gauge: '12GG', yarn: 'Merino 100%', qty: 14200, fob: 19.4, exf: '24 Oct', exfDays: 9, ship: 'Sea · Chattogram', status: 'critical', risk: 88, slip: 6, prob: 24, driver: '12GG knitting capacity 84% booked', merch: 'Rafiq H.', colours: 4, sizes: 'S–XXL' },
  { id: 'PO-26-1142', style: 'KW-5G-0391', desc: 'Cotton-acrylic half-zip', dept: 'Women', season: 'AW26', factory: 'F01', gauge: '5GG', yarn: 'Cotton 60 / Acrylic 40', qty: 12800, fob: 14.2, exf: '22 Oct', exfDays: 7, ship: 'Sea · Chattogram', status: 'critical', risk: 84, slip: 5, prob: 29, driver: 'Yarn in-house 6 days late', merch: 'Nusrat J.', colours: 2, sizes: 'XS–XL' },
  { id: 'PO-26-1221', style: 'KK-7G-0120', desc: "Kids' jumper, intarsia", dept: 'Kids', season: 'AW26', factory: 'F03', gauge: '7GG', yarn: 'Acrylic 100%', qty: 8400, fob: 9.6, exf: '27 Oct', exfDays: 12, ship: 'Sea · Chattogram', status: 'risk', risk: 76, slip: 4, prob: 41, driver: 'Mending backlog 2,300 pcs', merch: 'Tanvir A.', colours: 3, sizes: '2–12y' },
  { id: 'PO-26-1178', style: 'KM-7G-0640', desc: 'Lambswool V-neck pullover', dept: 'Men', season: 'AW26', factory: 'F02', gauge: '7GG', yarn: 'Lambswool 100%', qty: 10600, fob: 22.1, exf: '31 Oct', exfDays: 16, ship: 'Sea · Chattogram', status: 'risk', risk: 72, slip: 4, prob: 44, driver: 'Linking 900 pcs/day vs 1,300 needed', merch: 'Rafiq H.', colours: 3, sizes: 'S–XXL' },
  { id: 'PO-26-1156', style: 'KW-12G-0455', desc: 'Merino-blend turtleneck', dept: 'Women', season: 'AW26', factory: 'F03', gauge: '12GG', yarn: 'Merino 70 / Nylon 30', qty: 7200, fob: 21.7, exf: '26 Oct', exfDays: 11, ship: 'Sea · Chattogram', status: 'risk', risk: 69, slip: 3, prob: 48, driver: 'Yarn shade re-approval pending', merch: 'Tanvir A.', colours: 2, sizes: 'XS–L' },
  { id: 'PO-26-1194', style: 'KM-5G-0712', desc: 'Cotton cable cardigan', dept: 'Men', season: 'AW26', factory: 'F04', gauge: '5GG', yarn: 'Cotton 100%', qty: 9800, fob: 16.9, exf: '30 Oct', exfDays: 15, ship: 'Sea · Chattogram', status: 'risk', risk: 64, slip: 3, prob: 52, driver: 'Factory OTD 88% · knitting 91% loaded', merch: 'Farhana K.', colours: 3, sizes: 'S–XXL' },
  { id: 'PO-26-1209', style: 'KW-3G-0098', desc: 'Chunky wool-blend vest', dept: 'Women', season: 'AW26', factory: 'F05', gauge: '3GG', yarn: 'Wool 50 / Acrylic 50', qty: 4600, fob: 18.3, exf: '28 Oct', exfDays: 13, ship: 'Sea · Chattogram', status: 'risk', risk: 61, slip: 2, prob: 55, driver: 'Washing capacity shared with PO-26-1211', merch: 'Farhana K.', colours: 2, sizes: 'XS–XL' },
  { id: 'PO-26-1133', style: 'KK-5G-0104', desc: "Kids' crew-neck, striped", dept: 'Kids', season: 'AW26', factory: 'F05', gauge: '5GG', yarn: 'Acrylic 100%', qty: 6400, fob: 8.4, exf: '23 Oct', exfDays: 8, ship: 'Sea · Chattogram', status: 'risk', risk: 58, slip: 2, prob: 58, driver: 'Reporting gap · last update 13 Oct', merch: 'Tanvir A.', colours: 4, sizes: '2–12y' },
  { id: 'PO-26-1167', style: 'KM-14G-0902', desc: 'Fine-gauge merino polo', dept: 'Men', season: 'AW26', factory: 'F02', gauge: '14GG', yarn: 'Merino 100%', qty: 5200, fob: 26.4, exf: '25 Oct', exfDays: 10, ship: 'Sea · Chattogram', status: 'risk', risk: 56, slip: 2, prob: 60, driver: '14GG capacity 24 machines shared across 3 POs', merch: 'Rafiq H.', colours: 2, sizes: 'S–XL' },
  { id: 'PO-26-1098', style: 'KW-7G-0366', desc: 'Lambswool crew-neck', dept: 'Women', season: 'AW26', factory: 'F01', gauge: '7GG', yarn: 'Lambswool 100%', qty: 11200, fob: 21.2, exf: '09 Oct', exfDays: -6, ship: 'Air · Dhaka HSIA', status: 'late', risk: 97, slip: 11, prob: 0, driver: 'Past ex-factory · 2,400 pcs in packing', merch: 'Nusrat J.', colours: 3, sizes: 'XS–XL' },
  { id: 'PO-26-1104', style: 'KM-12G-0801', desc: 'Merino crew-neck', dept: 'Men', season: 'AW26', factory: 'F09', gauge: '12GG', yarn: 'Merino 100%', qty: 6800, fob: 19.9, exf: '12 Oct', exfDays: -3, ship: 'Air · Dhaka HSIA', status: 'late', risk: 95, slip: 4, prob: 0, driver: 'Final inspection failed 11 Oct · re-inspection 17 Oct', merch: 'Farhana K.', colours: 2, sizes: 'S–XXL' },
  { id: 'PO-26-1230', style: 'KW-12G-0470', desc: 'Merino cardigan, button-through', dept: 'Women', season: 'AW26', factory: 'F06', gauge: '12GG', yarn: 'Merino 100%', qty: 8800, fob: 23.6, exf: '05 Nov', exfDays: 21, ship: 'Sea · Chattogram', status: 'watch', risk: 38, slip: 0, prob: 78, driver: 'PP meeting 2 days late', merch: 'Nusrat J.', colours: 3, sizes: 'XS–XL' },
  { id: 'PO-26-1246', style: 'KM-5G-0730', desc: 'Cotton half-zip', dept: 'Men', season: 'AW26', factory: 'F07', gauge: '5GG', yarn: 'Cotton 100%', qty: 12400, fob: 15.1, exf: '08 Nov', exfDays: 24, ship: 'Sea · Chattogram', status: 'ok', risk: 14, slip: 0, prob: 94, driver: 'On plan', merch: 'Rafiq H.', colours: 4, sizes: 'S–XXL' },
  { id: 'PO-26-1251', style: 'KK-7G-0131', desc: "Kids' cardigan", dept: 'Kids', season: 'AW26', factory: 'F08', gauge: '7GG', yarn: 'Acrylic 100%', qty: 7600, fob: 9.9, exf: '10 Nov', exfDays: 26, ship: 'Sea · Chattogram', status: 'ok', risk: 11, slip: 0, prob: 95, driver: 'On plan', merch: 'Tanvir A.', colours: 3, sizes: '2–12y' },
  { id: 'PO-26-1240', style: 'KW-5G-0402', desc: 'Cotton-acrylic pullover', dept: 'Women', season: 'AW26', factory: 'F10', gauge: '5GG', yarn: 'Cotton 60 / Acrylic 40', qty: 10400, fob: 13.8, exf: '12 Nov', exfDays: 28, ship: 'Sea · Chattogram', status: 'ok', risk: 9, slip: 0, prob: 96, driver: 'On plan', merch: 'Farhana K.', colours: 3, sizes: 'XS–XL' },
  { id: 'PO-26-1119', style: 'KM-7G-0655', desc: 'Lambswool crew-neck', dept: 'Men', season: 'AW26', factory: 'F06', gauge: '7GG', yarn: 'Lambswool 100%', qty: 9200, fob: 21.9, exf: '14 Oct', exfDays: -1, ship: 'Sea · Chattogram', status: 'shipped', risk: 0, slip: 0, prob: 100, driver: 'Shipped 14 Oct · CTG', merch: 'Rafiq H.', colours: 3, sizes: 'S–XXL' },
  { id: 'PO-26-1261', style: 'KW-14G-0512', desc: 'Fine merino crew-neck', dept: 'Women', season: 'AW26', factory: 'F15', gauge: '14GG', yarn: 'Merino 100%', qty: 6200, fob: 27.2, exf: '18 Nov', exfDays: 34, ship: 'Sea · Chattogram', status: 'noupdate', risk: 45, slip: 0, prob: 70, driver: 'No report today', merch: 'Nusrat J.', colours: 2, sizes: 'XS–L' },
  { id: 'PO-27-0012', style: 'KW-14G-0601', desc: 'Fine-gauge cotton tee-knit', dept: 'Women', season: 'SS27', factory: 'F04', gauge: '14GG', yarn: 'Cotton 100%', qty: 15600, fob: 12.4, exf: '20 Jan', exfDays: 97, ship: 'Sea · Chattogram', status: 'watch', risk: 32, slip: 0, prob: 80, driver: 'Yarn booking not confirmed', merch: 'Farhana K.', colours: 5, sizes: 'XS–XL' },
  { id: 'PO-27-0018', style: 'KM-12G-0910', desc: 'Cotton-modal polo', dept: 'Men', season: 'SS27', factory: 'F07', gauge: '12GG', yarn: 'Cotton 70 / Modal 30', qty: 13200, fob: 13.9, exf: '28 Jan', exfDays: 105, ship: 'Sea · Chattogram', status: 'ok', risk: 12, slip: 0, prob: 93, driver: 'On plan', merch: 'Rafiq H.', colours: 4, sizes: 'S–XXL' },
];

// 8-week shipment outlook, pcs. Week starts Monday.
export const OUTLOOK = [
  { wk: 'W42', label: '12 Oct', ok: 142000, risk: 38000, crit: 21000, late: 18000 },
  { wk: 'W43', label: '19 Oct', ok: 168000, risk: 44000, crit: 27000, late: 0 },
  { wk: 'W44', label: '26 Oct', ok: 151000, risk: 52000, crit: 31000, late: 0 },
  { wk: 'W45', label: '02 Nov', ok: 139000, risk: 29000, crit: 9000, late: 0 },
  { wk: 'W46', label: '09 Nov', ok: 162000, risk: 24000, crit: 0, late: 0 },
  { wk: 'W47', label: '16 Nov', ok: 128000, risk: 18000, crit: 0, late: 0 },
  { wk: 'W48', label: '23 Nov', ok: 96000, risk: 12000, crit: 0, late: 0 },
  { wk: 'W49', label: '30 Nov', ok: 84000, risk: 6000, crit: 0, late: 0 },
];

// Factory × week risk heatmap (0 none … 4 critical; -1 no update)
export const HEAT = [
  { f: 'F01', v: [4, 4, 3, 2, 1, 1, 0, 0] },
  { f: 'F02', v: [3, 4, 3, 2, 2, 1, 0, 0] },
  { f: 'F03', v: [2, 3, 3, 2, 1, 0, 0, 0] },
  { f: 'F04', v: [1, 2, 2, 1, 1, 0, 0, 0] },
  { f: 'F05', v: [2, 2, 1, 1, 0, 0, 0, 0] },
  { f: 'F09', v: [3, 1, 1, 0, 0, 0, 0, 0] },
  { f: 'F11', v: [1, 1, 2, 1, 0, 0, 0, 0] },
  { f: 'F06', v: [0, 1, 1, 0, 0, 0, 0, 0] },
  { f: 'F15', v: [-1, -1, -1, -1, -1, -1, -1, -1] },
  { f: 'F20', v: [-1, -1, -1, -1, -1, -1, -1, -1] },
];

// Hero PO T&A. Day 0 = 1 Aug 2026 for positioning; dates as labels.
export const HERO_TA = [
  { m: 'Yarn booking', plan: '12 Aug', act: '12 Aug', pStart: 11, pEnd: 11, aStart: 11, aEnd: 11, state: 'done' },
  { m: 'Yarn shade approval', plan: '20 Aug', act: '22 Aug', pStart: 19, pEnd: 19, aStart: 21, aEnd: 21, state: 'done', lateBy: 2 },
  { m: 'Fit sample', plan: '28 Aug', act: '28 Aug', pStart: 27, pEnd: 27, aStart: 27, aEnd: 27, state: 'done' },
  { m: 'Size set', plan: '05 Sep', act: '07 Sep', pStart: 35, pEnd: 35, aStart: 37, aEnd: 37, state: 'done', lateBy: 2 },
  { m: 'PP sample approval', plan: '12 Sep', act: '15 Sep', pStart: 42, pEnd: 42, aStart: 45, aEnd: 45, state: 'done', lateBy: 3 },
  { m: 'PP meeting', plan: '15 Sep', act: '17 Sep', pStart: 45, pEnd: 45, aStart: 47, aEnd: 47, state: 'done', lateBy: 2 },
  { m: 'Yarn in-house', plan: '18 Sep', act: '26 Sep', pStart: 48, pEnd: 48, aStart: 56, aEnd: 56, state: 'done', lateBy: 8, flag: true },
  { m: 'Knitting', plan: '20 Sep – 12 Oct', act: '27 Sep – 18 Oct (fc)', pStart: 50, pEnd: 72, aStart: 57, aEnd: 78, state: 'running', lateBy: 6 },
  { m: 'Linking', plan: '28 Sep – 20 Oct', act: '09 Oct – 02 Nov (fc)', pStart: 58, pEnd: 80, aStart: 69, aEnd: 93, state: 'running', lateBy: 13, flag: true },
  { m: 'Trimming & mending', plan: '05 – 22 Oct', act: '14 Oct – 04 Nov (fc)', pStart: 65, pEnd: 82, aStart: 74, aEnd: 95, state: 'running', lateBy: 13 },
  { m: 'Washing', plan: '08 – 23 Oct', act: '17 Oct – 05 Nov (fc)', pStart: 68, pEnd: 83, aStart: 77, aEnd: 96, state: 'pending', lateBy: 13 },
  { m: 'Ironing & finishing', plan: '10 – 25 Oct', act: '19 Oct – 06 Nov (fc)', pStart: 70, pEnd: 85, aStart: 79, aEnd: 97, state: 'pending', lateBy: 12 },
  { m: 'Packing', plan: '14 – 27 Oct', act: '22 Oct – 06 Nov (fc)', pStart: 74, pEnd: 87, aStart: 82, aEnd: 97, state: 'pending', lateBy: 10 },
  { m: 'Final inspection (AQL)', plan: '28 Oct', act: '07 Nov (fc)', pStart: 88, pEnd: 88, aStart: 98, aEnd: 98, state: 'pending', lateBy: 10 },
  { m: 'Ex-factory', plan: '29 Oct', act: '07 Nov (fc)', pStart: 89, pEnd: 89, aStart: 98, aEnd: 98, state: 'pending', lateBy: 9, flag: true },
];

export const ALERTS = [
  { id: 'A1', t: '09:41', kind: 'PO turned critical', sev: 'critical', text: 'PO-26-1187 Lambswool cardigan · Ananta Knitwear · predicted 9 days late', po: 'PO-26-1187', owner: 'Nusrat J.', state: 'open' },
  { id: 'A2', t: '09:40', kind: 'Factory missed report', sev: 'noupdate', text: 'Halda Knit, Atrai Knitwear, Mahananda Woollens, Feni Knit Composite · no daily report by 09:30', owner: 'Merchandising', state: 'open' },
  { id: 'A3', t: '08:52', kind: 'Yarn in-house late', sev: 'risk', text: 'PO-26-1142 Cotton-acrylic half-zip · yarn in-house 6 days late at Ananta Knitwear', po: 'PO-26-1142', owner: 'Nusrat J.', state: 'open' },
  { id: 'A4', t: 'Yesterday 17:10', kind: 'Inspection failed', sev: 'critical', text: 'PO-26-1104 Merino crew-neck · final AQL failed at Bhairab Knitting · 14 holes / 80 sampled', po: 'PO-26-1104', owner: 'QA · Imran S.', state: 'assigned' },
  { id: 'A5', t: 'Yesterday 14:22', kind: 'PO turned at risk', sev: 'risk', text: 'PO-26-1203 Merino crew-neck · 12GG capacity 84% booked at Meghna Knitwear', po: 'PO-26-1203', owner: 'Rafiq H.', state: 'open' },
  { id: 'A6', t: '13 Oct 10:05', kind: 'PO turned at risk', sev: 'risk', text: 'PO-26-1221 Kids jumper · mending backlog 2,300 pcs at Padma Woollens', po: 'PO-26-1221', owner: 'Tanvir A.', state: 'snoozed' },
  { id: 'A7', t: '13 Oct 09:12', kind: 'Reporting compliance', sev: 'watch', text: 'Mahananda Woollens reporting compliance fell to 72% (30-day)', owner: 'Merchandising', state: 'acked' },
];

export const UPLOADS = [
  { file: 'Ananta_DPR_15Oct2026.xlsx', factory: 'Ananta Knitwear', by: 'Nusrat J.', at: '09:12', rows: 184, warn: 3, err: 0, status: 'ok' },
  { file: 'Meghna_Daily_Output_15-10-26.xlsx', factory: 'Meghna Knitwear', by: 'Rafiq H.', at: '08:51', rows: 162, warn: 0, err: 0, status: 'ok' },
  { file: 'Padma_Production_15Oct.xlsx', factory: 'Padma Woollens', by: 'Tanvir A.', at: '11:40', rows: 141, warn: 6, err: 2, status: 'err' },
  { file: 'Jamuna_DPR_2026-10-15.xlsx', factory: 'Jamuna Knit Composite', by: 'Farhana K.', at: '08:20', rows: 158, warn: 1, err: 0, status: 'ok' },
  { file: 'Surma_Output_15.10.xlsx', factory: 'Surma Sweaters', by: 'Farhana K.', at: '09:05', rows: 112, warn: 2, err: 0, status: 'ok' },
];
