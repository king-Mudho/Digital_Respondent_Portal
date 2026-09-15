// Shared layout for the ABF-FST portal manuals: a tiny block language
// (h1/p/steps/table/img/...) rendered to Word with docx-js.
const fs = require("fs");
const path = require("path");
const {
  AlignmentType, BorderStyle, Document, Footer, Header, HeadingLevel, ImageRun, LevelFormat, PageBreak,
  PageNumber, Paragraph, ShadingType, Table, TableCell, TableOfContents, TableRow, TabStopType, TextRun, WidthType,
  VerticalAlign,
} = require("docx");

const SCREENS = path.resolve(__dirname, "../../manuals/screens");
const C = {
  navy: "1B3350", navyDark: "122238", gold: "A67C27", ink: "22282E", muted: "5B6670", line: "D5DAE0",
  wash: "F1F4F7", tipBg: "EAF2FA", tipLine: "2A6FB0", warnBg: "FBF1E1", warnLine: "D9A441",
};
const FONT = "Calibri";
const PAGE_W = 11906; // A4 in DXA
const MARGIN = 1247; // 2.2 cm
const CONTENT_W = PAGE_W - 2 * MARGIN; // 9412 DXA = 6.54 in

// "**bold**", "`code`" and "_italic_" inline markup.
function runs(text, base = {}) {
  const out = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`|_[^_]+_)/g;
  let last = 0;
  for (const m of String(text).matchAll(re)) {
    if (m.index > last) out.push(new TextRun({ text: text.slice(last, m.index), ...base }));
    const t = m[0];
    if (t.startsWith("**")) out.push(new TextRun({ text: t.slice(2, -2), bold: true, ...base }));
    else if (t.startsWith("`")) out.push(new TextRun({ text: t.slice(1, -1), font: "Consolas", size: (base.size ?? 21) - 2, color: C.navyDark, ...base, bold: false }));
    else out.push(new TextRun({ text: t.slice(1, -1), italics: true, ...base }));
    last = m.index + t.length;
  }
  if (last < String(text).length) out.push(new TextRun({ text: String(text).slice(last), ...base }));
  return out;
}

function jpegSize(file) {
  const buf = fs.readFileSync(file);
  let i = 2;
  while (i < buf.length) {
    if (buf[i] !== 0xff) { i += 1; continue; }
    const marker = buf[i + 1];
    const len = buf.readUInt16BE(i + 2);
    if (marker >= 0xc0 && marker <= 0xc3) return { height: buf.readUInt16BE(i + 5), width: buf.readUInt16BE(i + 7), buf };
    i += 2 + len;
  }
  throw new Error(`no size in ${file}`);
}

function cell(children, { width, fill, bold = false, color, margins = true } = {}) {
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    shading: fill ? { fill, type: ShadingType.CLEAR, color: "auto" } : undefined,
    margins: margins ? { top: 70, bottom: 70, left: 110, right: 110 } : undefined,
    verticalAlign: VerticalAlign.TOP,
    children: (Array.isArray(children) ? children : [children]).map((c) =>
      typeof c === "string" ? new Paragraph({ spacing: { after: 40 }, children: runs(c, { size: 19, bold, color }) }) : c),
  });
}

const border = (color = C.line, size = 4) => ({ style: BorderStyle.SINGLE, size, color });

class Builder {
  constructor({ title, short, subtitle, audience, revision }) {
    Object.assign(this, { title, short, subtitle, audience, revision });
    this.children = [];
    this.figure = 0;
    this.stepLists = 0;
    this.numberingConfigs = [];
  }

  add(blocks) {
    for (const b of blocks) this.block(b);
    return this;
  }

  block(b) {
    const [kind, ...a] = b;
    const push = (x) => this.children.push(x);
    switch (kind) {
      case "h1": push(new Paragraph({ heading: HeadingLevel.HEADING_1, pageBreakBefore: true, children: [new TextRun(a[0])] })); break;
      case "h2": push(new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(a[0])] })); break;
      case "h3": push(new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun(a[0])] })); break;
      case "p": push(new Paragraph({ spacing: { after: 120, line: 288 }, children: runs(a[0]) })); break;
      case "small": push(new Paragraph({ spacing: { after: 100 }, children: runs(a[0], { size: 18, color: C.muted }) })); break;
      case "bullets":
        for (const item of a[0]) push(new Paragraph({ numbering: { reference: "bullets", level: 0 }, spacing: { after: 60, line: 276 }, children: runs(item) }));
        push(new Paragraph({ spacing: { after: 60 }, children: [] }));
        break;
      case "steps": this.steps(a[0]); break;
      case "table": push(this.table(a[0], a[1], a[2])); push(new Paragraph({ spacing: { after: 120 }, children: [] })); break;
      case "kv": push(this.table(null, a[0], a[1] ?? [0.3, 0.7], { keyColumn: true })); push(new Paragraph({ spacing: { after: 120 }, children: [] })); break;
      case "tip": push(this.callout(a[0], a[1], C.tipBg, C.tipLine)); break;
      case "warn": push(this.callout(a[0], a[1], C.warnBg, C.warnLine)); break;
      case "img": for (const x of this.image(a[0], a[1], a[2] ?? {})) push(x); break;
      case "pagebreak": push(new Paragraph({ children: [new PageBreak()] })); break;
      default: throw new Error(`unknown block ${kind}`);
    }
  }

  steps(items) {
    const ref = `steps-${this.stepLists++}`;
    this.numberingConfigs.push({
      reference: ref,
      levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 460, hanging: 360 } }, run: { bold: true, color: C.gold } } }],
    });
    for (const item of items) {
      const it = typeof item === "string" ? { text: item } : item;
      this.children.push(new Paragraph({ numbering: { reference: ref, level: 0 }, spacing: { after: 80, line: 276 }, children: runs(it.text) }));
      if (it.sub) for (const s of it.sub) this.children.push(new Paragraph({ numbering: { reference: "bullets", level: 1 }, spacing: { after: 40 }, children: runs(s) }));
      if (it.img) for (const x of this.image(it.img, it.caption, { indent: true, ...(it.opts ?? {}) })) this.children.push(x);
    }
    this.children.push(new Paragraph({ spacing: { after: 80 }, children: [] }));
  }

  table(headers, rows, fractions, { keyColumn = false } = {}) {
    const n = (headers ?? rows[0]).length;
    const fr = fractions ?? Array(n).fill(1 / n);
    const widths = fr.map((f) => Math.round(f * CONTENT_W));
    widths[widths.length - 1] = CONTENT_W - widths.slice(0, -1).reduce((s, w) => s + w, 0);
    const trs = [];
    if (headers) trs.push(new TableRow({ tableHeader: true, children: headers.map((h, i) => cell(h, { width: widths[i], fill: C.navy, bold: true, color: "FFFFFF" })) }));
    rows.forEach((r, ri) => trs.push(new TableRow({ cantSplit: true, children: r.map((v, i) => cell(v, {
      width: widths[i], fill: keyColumn && i === 0 ? C.wash : (!keyColumn && ri % 2 === 1 ? "F8FAFB" : undefined), bold: keyColumn && i === 0,
    })) })));
    return new Table({
      width: { size: CONTENT_W, type: WidthType.DXA }, columnWidths: widths, rows: trs,
      borders: { top: border(), bottom: border(), left: border(), right: border(), insideHorizontal: border(), insideVertical: border() },
    });
  }

  callout(title, body, fill, line) {
    const paras = [];
    if (title) paras.push(new Paragraph({ spacing: { after: 40 }, children: [new TextRun({ text: title, bold: true, size: 20, color: C.ink })] }));
    for (const part of [].concat(body)) paras.push(new Paragraph({ spacing: { after: 40, line: 264 }, children: runs(part, { size: 19 }) }));
    return new Table({
      width: { size: CONTENT_W, type: WidthType.DXA }, columnWidths: [CONTENT_W],
      borders: { top: border(fill, 2), bottom: border(fill, 2), right: border(fill, 2), left: { style: BorderStyle.SINGLE, size: 24, color: line }, insideHorizontal: border(fill), insideVertical: border(fill) },
      rows: [new TableRow({ cantSplit: true, children: [new TableCell({ width: { size: CONTENT_W, type: WidthType.DXA }, shading: { fill, type: ShadingType.CLEAR, color: "auto" },
        margins: { top: 100, bottom: 100, left: 180, right: 160 }, children: paras })] })],
    });
  }

  image(file, caption, { width, maxHeight = 520, indent = false, phone = false } = {}) {
    const full = path.join(SCREENS, file);
    const { width: w, height: h, buf } = jpegSize(full);
    let outW = width ?? (phone ? 260 : (indent ? 560 : 600));
    let outH = Math.round((h / w) * outW);
    const cap = phone ? Math.max(maxHeight, 520) : maxHeight;
    if (outH > cap) { outW = Math.round(outW * (cap / outH)); outH = cap; }
    this.figure += 1;
    const items = [new Paragraph({
      alignment: AlignmentType.CENTER, keepNext: true, spacing: { before: 80, after: 40 },
      children: [new ImageRun({ type: "jpg", data: buf, transformation: { width: outW, height: outH },
        altText: { title: caption ?? file, description: caption ?? file, name: file } })],
    })];
    if (caption) items.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 180 },
      children: [new TextRun({ text: `Figure ${this.figure}. `, bold: true, size: 17, color: C.muted }), ...runs(caption, { size: 17, color: C.muted, italics: true })] }));
    return items;
  }

  cover() {
    const spacer = (n) => new Paragraph({ spacing: { after: n }, children: [] });
    const meta = [
      ["Study", "Developing and Validating the Agribusiness Bankability Framework for Food Systems Transformation through Novel Financing Models in Zimbabwe (ABF-FST)"],
      ["Principal Researcher", "Happyson Saina, Doctor of Strategic Management candidate, Chinhoyi University of Technology"],
      ["Supervisors", "Dr L. Chikazhe and Dr J. Kanyepe"],
      ["For", this.audience],
      ["System address", "https://research.agribizframework.com"],
      ["Contact", "0773943709 · abffst.research.cut@gmail.com"],
      ["Version", this.revision],
    ];
    const widths = [2300, CONTENT_W - 2300];
    return [
      spacer(1400),
      new Paragraph({ spacing: { after: 120 }, children: [new TextRun({ text: "CHINHOYI UNIVERSITY OF TECHNOLOGY · ABF-FST RESEARCH STUDY", bold: true, size: 20, color: C.gold, characterSpacing: 20 })] }),
      new Paragraph({ spacing: { after: 160 }, border: { bottom: { style: BorderStyle.SINGLE, size: 18, color: C.gold, space: 12 } },
        children: [new TextRun({ text: this.title, bold: true, size: 56, color: C.navyDark })] }),
      new Paragraph({ spacing: { after: 700, line: 300 }, children: [new TextRun({ text: this.subtitle, size: 28, color: C.muted })] }),
      new Table({
        width: { size: CONTENT_W, type: WidthType.DXA }, columnWidths: widths,
        borders: { top: border(), bottom: border(), left: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" }, right: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" }, insideHorizontal: border(), insideVertical: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" } },
        rows: meta.map(([k, v]) => new TableRow({ children: [
          cell(k.toUpperCase(), { width: widths[0], bold: true, color: C.gold }),
          cell(v, { width: widths[1] }),
        ] })),
      }),
      spacer(500),
      new Paragraph({ children: runs("Screenshots in this document use **fictional demonstration data**. Organisation and person names, phone numbers and figures shown in them are not real study records.", { size: 18, color: C.muted, italics: true }) }),
      new Paragraph({ children: [new PageBreak()] }),
      new Paragraph({ spacing: { after: 200 }, children: [new TextRun({ text: "Contents", bold: true, size: 36, color: C.navyDark })] }),
      new TableOfContents("Contents", { hyperlink: true, headingStyleRange: "1-2" }),
    ];
  }

  save(file) {
    const doc = new Document({
      creator: "ABF-FST research team",
      title: this.title,
      description: this.subtitle,
      features: { updateFields: true },
      styles: {
        default: { document: { run: { font: FONT, size: 21, color: C.ink } } },
        paragraphStyles: [
          { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
            run: { size: 36, bold: true, color: C.navyDark, font: FONT },
            paragraph: { spacing: { before: 120, after: 200 }, outlineLevel: 0, border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: C.gold, space: 6 } } } },
          { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
            run: { size: 28, bold: true, color: C.navy, font: FONT }, paragraph: { spacing: { before: 300, after: 120 }, outlineLevel: 1, keepNext: true } },
          { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
            run: { size: 23, bold: true, color: C.ink, font: FONT }, paragraph: { spacing: { before: 220, after: 80 }, outlineLevel: 2, keepNext: true } },
        ],
      },
      numbering: {
        config: [
          { reference: "bullets", levels: [
            { level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 460, hanging: 280 } } } },
            { level: 1, format: LevelFormat.BULLET, text: "–", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 900, hanging: 280 } } } },
          ] },
          ...this.numberingConfigs,
        ],
      },
      sections: [{
        properties: { page: { size: { width: PAGE_W, height: 16838 }, margin: { top: 1300, bottom: 1200, left: MARGIN, right: MARGIN } }, titlePage: true },
        headers: {
          default: new Header({ children: [new Paragraph({ border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: C.line, space: 4 } },
            tabStops: [{ type: TabStopType.RIGHT, position: CONTENT_W }],
            children: [new TextRun({ text: "ABF-FST DIGITAL RESPONDENT PORTAL", bold: true, size: 16, color: C.navy }), new TextRun({ text: `\t${this.short}`, size: 16, color: C.muted })] })] }),
          first: new Header({ children: [new Paragraph({ children: [] })] }),
        },
        footers: {
          default: new Footer({ children: [new Paragraph({ tabStops: [{ type: TabStopType.RIGHT, position: CONTENT_W }],
            children: [new TextRun({ text: `${this.revision}`, size: 16, color: C.muted }),
              new TextRun({ children: ["\tPage ", PageNumber.CURRENT, " of ", PageNumber.TOTAL_PAGES], size: 16, color: C.muted })] })] }),
          first: new Footer({ children: [new Paragraph({ children: [] })] }),
        },
        children: [...this.cover(), ...this.children],
      }],
    });
    return require("docx").Packer.toBuffer(doc).then((b) => fs.writeFileSync(file, b));
  }
}

module.exports = { Builder };
