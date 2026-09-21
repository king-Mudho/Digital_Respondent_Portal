// Builds the Word user manuals into docs/manuals/:
//   the System Manual, one Role Guide per role, the Respondent Guide, and the
//   Research Assistant training programme and manual.
//
//   cd docs/tools && npm install && node build_manuals.js
//   powershell -File finalise_manuals.ps1   # Windows + Word: fills the tables of contents, writes PDFs
//
// Content lives in manuals/*.js; screenshots in docs/manuals/screens/ come
// from fictional demonstration data, never the live registers.
const path = require("path");
const fs = require("fs");
const { Builder } = require("./manuals/lib");

const OUT = path.resolve(__dirname, "../manuals");
fs.mkdirSync(OUT, { recursive: true });

const docs = [require("./manuals/system"), require("./manuals/reference").referenceDoc(), ...require("./manuals/roles"), require("./manuals/respondent"), ...require("./manuals/training")];

// `node build_manuals.js RA_` rebuilds only the documents whose file name starts with RA_.
const only = process.argv[2];

(async () => {
  for (const d of docs.filter((doc) => !only || doc.file.startsWith(only))) {
    const file = path.join(OUT, `${d.file}.docx`);
    await new Builder(d.meta).add(d.blocks).save(file);
    console.log("wrote", path.relative(process.cwd(), file));
  }
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
