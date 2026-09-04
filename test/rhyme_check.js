/* node test/rhyme_check.js — fails loudly if the rime keying regresses. */
const fs=require('fs'), assert=require('assert'), path=require('path');
const html=fs.readFileSync(path.join(__dirname,'..','index.html'),'utf8');

function grab(name){
  const i=html.indexOf('function '+name+'(');
  assert.ok(i>0, 'missing '+name);
  let d=0, j=html.indexOf('{',i);
  for(let k=j;k<html.length;k++){ if(html[k]==='{')d++; else if(html[k]==='}'){ d--; if(!d) return html.slice(i,k+1); } }
  throw new Error('unbalanced '+name);
}
function grabConst(name){
  const i=html.indexOf('const '+name+'=');
  assert.ok(i>0,'missing '+name);
  const end=html.indexOf('\nfunction ',i);
  return html.slice(i, html.indexOf(';\n',i)>0 && html.indexOf(';\n',i)<end ? html.indexOf(';\n',i)+1 : end);
}
const src=[grabConst('VOWNAME'),grabConst('CODA_RULES'),grabConst('IRREG'),grabConst('LONGEN'),
           grab('clean'),grab('phon'),grab('codaClass'),grab('syllables'),grab('rhymeParts')].join('\n');
const rhymeParts=new Function(src+'\nreturn rhymeParts;')();

const key=w=>rhymeParts(w).key, vow=w=>rhymeParts(w).vowel, key2=w=>rhymeParts(w).key2;

// true rhymes share the full rime
assert.strictEqual(key('bucks'), key('sucks'));
assert.strictEqual(key('run'), key('done'));
assert.strictEqual(key('night'), key('light'));
assert.strictEqual(key('season'), key('reason'));

// coda matters: near-rhymes must NOT collapse into the same family
assert.notStrictEqual(key('bucks'), key('fuck'));
assert.notStrictEqual(key('run'), key('bucks'));

// but they still share a vowel, which is what drives the softer shade
assert.strictEqual(vow('bucks'), vow('fuck'));

// multisyllabic: two-syllable rime must match on the multi, not just the shared "-ated" tail
assert.strictEqual(key2('escalated'), key2('medicated'));
assert.strictEqual(key2('season'), key2('reason'));
assert.strictEqual(key2('later'), key2('traitor'));  // open syllable: LAY-ter / TRAY-tor
assert.notStrictEqual(key2('later'), key2('paper')); // LAY-ter vs PAY-per: assonance, not a multi

// multi-word tail chains rhyme as a unit: "seasonal reason" / "even a demon"
const tail=ws=>ws.map(key).join('|');
assert.strictEqual(tail(['a','reason']), tail(['a','season']));
assert.notStrictEqual(tail(['a','reason']), tail(['a','river']));

console.log('rhyme_check ok');
