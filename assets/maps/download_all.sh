#!/bin/bash

# Rainbow Six Siege Map Blueprint Downloader
# Uses browser headers to bypass anti-hotlinking

MAPS=(
  "bank:银行:4"
  "chalet:木屋:4"
  "kafe-dostoyevsky:杜斯妥也夫斯基咖啡馆:4"
  "border:边境:4"
  "clubhouse:俱乐部会所:4"
  "stadium-alpha:A号竞技场:3"
  "stadium-bravo:B号竞技场:3"
  "lair:虎穴狼巢:4"
  "nighthaven-labs:永夜安港实验室:4"
  "close-quarter:近距离战斗:3"
  "emerald-plains:翡翠原:4"
  "coastline:海岸线:3"
  "consulate:领事馆:4"
  "favela:贫民窟:4"
  "fortress:要塞:4"
  "hereford-base:赫里福基地:4"
  "house:芝加哥豪宅:3"
  "kanal:运河:4"
  "oregon:俄勒冈乡间屋宅:4"
  "outback:荒漠服务站:3"
  "presidential-plane:总统专机:3"
  "skyscraper:摩天大楼:4"
  "theme-park:主题公园:4"
  "tower:塔楼:5"
  "villa:庄园:4"
  "yacht:游艇:4"
)

BASE_URL="https://cdn.hommk.com/pcgame/ubi2015/img/gamezone/r6/new/maps"
OUTPUT_DIR="/home/node/clawd/little-herta/assets/maps"
REFERER="https://zh-cn.ubisoft.com/r6s/maps"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Floor name mapping based on blueprint number
# Blueprint-1 could be basement or 1f depending on map
# We'll use: b1, 1f, 2f, roof, top

for entry in "${MAPS[@]}"; do
  IFS=':' read -r map_key map_name num_floors <<< "$entry"
  
  echo "=== Processing $map_key ($map_name) ==="
  
  # Create directory for the map
  mkdir -p "$OUTPUT_DIR/$map_key"
  
  # Download each floor blueprint
  for floor_num in $(seq 1 $num_floors); do
    # Determine floor name
    case $floor_num in
      1) floor_name="b1" ;;
      2) floor_name="1f" ;;
      3) floor_name="2f" ;;
      4) floor_name="roof" ;;
      5) floor_name="top" ;;
      *) floor_name="floor${floor_num}" ;;
    esac
    
    url="${BASE_URL}/r6-maps-${map_key}-blueprint-${floor_num}.jpg"
    output_file="$OUTPUT_DIR/$map_key/${floor_name}.png"
    
    # Skip if already downloaded
    if [ -f "$output_file" ]; then
      file_type=$(file -b "$output_file")
      if echo "$file_type" | grep -q "JPEG\|PNG"; then
        echo "  [SKIP] $floor_name already exists"
        continue
      fi
    fi
    
    echo "  Downloading $floor_name from blueprint-$floor_num..."
    
    /usr/bin/curl -L -s -o "$output_file" \
      -H "User-Agent: $UA" \
      -H "Referer: $REFERER" \
      "$url"
    
    # Verify the download
    if [ -f "$output_file" ]; then
      file_type=$(file -b "$output_file")
      if echo "$file_type" | grep -q "JPEG\|PNG"; then
        echo "    [OK] Saved: $(basename "$output_file")"
      else
        echo "    [FAIL] Not an image: $file_type"
        rm -f "$output_file"
      fi
    else
      echo "    [FAIL] File not created"
    fi
    
    sleep 0.3
  done
  
  echo ""
done

echo "=== All maps processed! ==="