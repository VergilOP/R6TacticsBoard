#!/bin/bash

# Rainbow Six Siege Map Blueprint Downloader
# Maps all have 4 floors: b1 (basement), 1f, 2f, roof

MAPS=(
  "bank"
  "chalet"
  "kafe-dostoyevsky"
  "border"
  "clubhouse"
  "stadium-alpha"
  "stadium-bravo"
  "lair"
  "nighthaven-labs"
  "close-quarter"
  "emerald-plains"
  "coastline"
  "consulate"
  "favela"
  "fortress"
  "hereford-base"
  "house"
  "kanal"
  "oregon"
  "outback"
  "presidential-plane"
  "skyscraper"
  "theme-park"
  "tower"
  "villa"
  "yacht"
)

BASE_URL="https://cdn.hommk.com/pcgame/ubi2015/img/gamezone/r6/new/maps"
OUTPUT_DIR="/home/node/clawd/little-herta/assets/maps"

# Floor mapping: blueprint-1 = b1 (basement), blueprint-2 = 1f, blueprint-3 = 2f, blueprint-4 = roof
declare -A FLOOR_MAP=( ["1"]="b1" ["2"]="1f" ["3"]="2f" ["4"]="roof" )

for map_key in "${MAPS[@]}"; do
  echo "Processing $map_key..."
  
  # Create directory for the map
  mkdir -p "$OUTPUT_DIR/$map_key"
  
  # Download each floor blueprint
  for floor_num in 1 2 3 4; do
    floor_name="${FLOOR_MAP[$floor_num]}"
    url="${BASE_URL}/r6-maps-${map_key}-blueprint-${floor_num}.jpg"
    output_file="$OUTPUT_DIR/$map_key/${floor_name}.png"
    
    echo "  Downloading $floor_name from $url"
    /usr/bin/curl -L -s -o "$output_file" "$url"
    
    # Check if the file is a valid image (not HTML 403 error)
    if file "$output_file" | grep -q "JPEG\|PNG"; then
      echo "  Successfully downloaded $floor_name"
    else
      echo "  Failed to download $floor_name (may not exist)"
      rm -f "$output_file"
    fi
  done
  
  echo "Completed $map_key"
  echo ""
done

echo "All maps processed!"