#!/usr/bin/env node

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

// Map configuration: key -> number of floors
const MAPS = {
  'bank': { name: '银行', floors: 4 },
  'chalet': { name: '木屋', floors: 4 },
  'kafe-dostoyevsky': { name: '杜斯妥也夫斯基咖啡馆', floors: 4 },
  'border': { name: '边境', floors: 4 },
  'clubhouse': { name: '俱乐部会所', floors: 4 },
  'stadium-alpha': { name: 'A号竞技场', floors: 3 },
  'stadium-bravo': { name: 'B号竞技场', floors: 3 },
  'lair': { name: '虎穴狼巢', floors: 4 },
  'nighthaven-labs': { name: '永夜安港实验室', floors: 4 },
  'close-quarter': { name: '近距离战斗', floors: 3 },
  'emerald-plains': { name: '翡翠原', floors: 4 },
  'coastline': { name: '海岸线', floors: 3 },
  'consulate': { name: '领事馆', floors: 4 },
  'favela': { name: '贫民窟', floors: 4 },
  'fortress': { name: '要塞', floors: 4 },
  'hereford-base': { name: '赫里福基地', floors: 4 },
  'house': { name: '芝加哥豪宅', floors: 3 },
  'kanal': { name: '运河', floors: 4 },
  'oregon': { name: '俄勒冈乡间屋宅', floors: 4 },
  'outback': { name: '荒漠服务站', floors: 3 },
  'presidential-plane': { name: '总统专机', floors: 3 },
  'skyscraper': { name: '摩天大楼', floors: 4 },
  'theme-park': { name: '主题公园', floors: 4 },
  'tower': { name: '塔楼', floors: 5 },
  'villa': { name: '庄园', floors: 4 },
  'yacht': { name: '游艇', floors: 4 }
};

const BASE_URL = 'https://cdn.hommk.com/pcgame/ubi2015/img/gamezone/r6/new/maps';
const OUTPUT_DIR = '/home/node/clawd/little-herta/assets/maps';
const SCREENSHOT_DIR = '/home/node/.openclaw/media/browser';

// Floor mapping for bank (4 floors): blueprint-1 = b1, blueprint-2 = 1f, blueprint-3 = 2f, blueprint-4 = roof
// Different maps may have different floor configurations

async function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function getBlueprintUrl(mapKey, floorNum) {
  return `${BASE_URL}/r6-maps-${mapKey}-blueprint-${floorNum}.jpg`;
}

async function downloadMapBlueprints(mapKey, mapInfo) {
  console.log(`\n=== Processing ${mapKey} (${mapInfo.name}) ===`);
  
  const mapDir = path.join(OUTPUT_DIR, mapKey);
  if (!fs.existsSync(mapDir)) {
    fs.mkdirSync(mapDir, { recursive: true });
  }
  
  const numFloors = mapInfo.floors;
  
  for (let floor = 1; floor <= numFloors; floor++) {
    const url = getBlueprintUrl(mapKey, floor);
    console.log(`  Floor ${floor}: ${url}`);
    
    // Use curl with browser-like headers to bypass anti-hotlinking
    const floorNames = ['b1', '1f', '2f', 'roof', 'top'];
    const floorName = floorNames[floor - 1] || `floor${floor}`;
    const outputPath = path.join(mapDir, `${floorName}.png`);
    
    try {
      // Try with curl and browser headers
      const cmd = `/usr/bin/curl -L -s -o "${outputPath}" \
        -H "User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36" \
        -H "Referer: https://zh-cn.ubisoft.com/r6s/maps" \
        "${url}"`;
      
      execSync(cmd, { stdio: 'pipe' });
      
      // Check if file is valid
      const fileCheck = execSync(`file "${outputPath}"`).toString();
      if (fileCheck.includes('JPEG') || fileCheck.includes('PNG')) {
        console.log(`    Success: saved to ${outputPath}`);
      } else {
        console.log(`    Failed: got non-image file`);
        fs.unlinkSync(outputPath);
      }
    } catch (err) {
      console.log(`    Error: ${err.message}`);
    }
    
    await sleep(500);
  }
}

async function main() {
  console.log('Rainbow Six Siege Map Blueprint Downloader');
  console.log('=========================================\n');
  
  // Create output directory
  if (!fs.existsSync(OUTPUT_DIR)) {
    fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  }
  
  const mapKeys = Object.keys(MAPS);
  let processed = 0;
  let skipped = 0;
  
  for (const mapKey of mapKeys) {
    const mapInfo = MAPS[mapKey];
    
    // Check if already processed
    const mapDir = path.join(OUTPUT_DIR, mapKey);
    if (fs.existsSync(mapDir)) {
      const existingFiles = fs.readdirSync(mapDir).filter(f => f.endsWith('.png'));
      if (existingFiles.length >= mapInfo.floors) {
        console.log(`Skipping ${mapKey} - already processed (${existingFiles.length} files)`);
        skipped++;
        continue;
      }
    }
    
    await downloadMapBlueprints(mapKey, mapInfo);
    processed++;
    
    // Save progress every 5 maps
    if (processed % 5 === 0) {
      console.log(`\nProgress: ${processed} maps processed, ${skipped} skipped`);
    }
  }
  
  console.log('\n=========================================');
  console.log(`Download complete!`);
  console.log(`Processed: ${processed} maps`);
  console.log(`Skipped: ${skipped} maps`);
}

main().catch(console.error);