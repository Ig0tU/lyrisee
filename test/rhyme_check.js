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
const src=[grabConst('VOWNAME'),grabConst('CODA_RULES'),grabConst('IRREG'),
           grab('clean'),grab('phon'),grab('codaClass'),grab('rhymeParts')].join('\n');
const rhymeParts=new Function(src+'\nreturn rhymeParts;')();

const key=w=>rhymeParts(w).key, vow=w=>rhymeParts(w).vowel;

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

console.log('rhyme_check ok');
