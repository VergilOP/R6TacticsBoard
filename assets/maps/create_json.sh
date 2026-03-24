#!/bin/bash

# Create map.json for each map

create_map_json() {
  local map_key="$1"
  local map_name="$2"
  local map_dir="$3"
  local num_floors="$4"
  
  # Determine floor files based on map
  local floors_json=""
  
  case "$map_key" in
    bank)
      floors_json='[
        {"key": "b1", "name": "Basement", "image": "assets/maps/bank/b1.png"},
        {"key": "1f", "name": "First Floor", "image": "assets/maps/bank/1f.png"},
        {"key": "2f", "name": "Second Floor", "image": "assets/maps/bank/2f.png"},
        {"key": "roof", "name": "Roof", "image": "assets/maps/bank/roof.png"}
      ]'
      ;;
    chalet)
      floors_json='[
        {"key": "b1", "name": "Basement", "image": "assets/maps/chalet/b1.png"},
        {"key": "1f", "name": "First Floor", "image": "assets/maps/chalet/1f.png"},
        {"key": "2f", "name": "Second Floor", "image": "assets/maps/chalet/2f.png"},
        {"key": "roof", "name": "Roof", "image": "assets/maps/chalet/roof.png"}
      ]'
      ;;
    kafe-dostoyevsky)
      floors_json='[
        {"key": "b1", "name": "Basement", "image": "assets/maps/kafe-dostoyevsky/b1.png"},
        {"key": "1f", "name": "First Floor", "image": "assets/maps/kafe-dostoyevsky/1f.png"},
        {"key": "2f", "name": "Second Floor", "image": "assets/maps/kafe-dostoyevsky/2f.png"},
        {"key": "roof", "name": "Roof", "image": "assets/maps/kafe-dostoyevsky/roof.png"}
      ]'
      ;;
    border)
      floors_json='[
        {"key": "1f", "name": "First Floor", "image": "assets/maps/border/1f.png"},
        {"key": "2f", "name": "Second Floor", "image": "assets/maps/border/2f.png"},
        {"key": "roof", "name": "Roof", "image": "assets/maps/border/roof.png"}
      ]'
      ;;
    clubhouse)
      floors_json='[
        {"key": "b1", "name": "Basement", "image": "assets/maps/clubhouse/b1.png"},
        {"key": "1f", "name": "First Floor", "image": "assets/maps/clubhouse/1f.png"},
        {"key": "2f", "name": "Second Floor", "image": "assets/maps/clubhouse/2f.png"},
        {"key": "roof", "name": "Roof", "image": "assets/maps/clubhouse/roof.png"}
      ]'
      ;;
    stadium-alpha)
      floors_json='[
        {"key": "b1", "name": "Basement", "image": "assets/maps/stadium-alpha/b1.png"},
        {"key": "1f", "name": "Ground Floor", "image": "assets/maps/stadium-alpha/1f.png"},
        {"key": "2f", "name": "First Floor", "image": "assets/maps/stadium-alpha/2f.png"},
        {"key": "3f", "name": "Second Floor", "image": "assets/maps/stadium-alpha/3f.png"},
        {"key": "roof", "name": "Roof", "image": "assets/maps/stadium-alpha/roof.png"}
      ]'
      ;;
    stadium-bravo)
      floors_json='[
        {"key": "b1", "name": "Basement", "image": "assets/maps/stadium-bravo/b1.png"},
        {"key": "1f", "name": "First Floor", "image": "assets/maps/stadium-bravo/1f.png"},
        {"key": "2f", "name": "Second Floor", "image": "assets/maps/stadium-bravo/2f.png"},
        {"key": "roof", "name": "Roof", "image": "assets/maps/stadium-bravo/roof.png"}
      ]'
      ;;
    lair)
      floors_json='[
        {"key": "b1", "name": "Basement", "image": "assets/maps/lair/b1.png"},
        {"key": "1f", "name": "First Floor", "image": "assets/maps/lair/1f.png"},
        {"key": "2f", "name": "Second Floor", "image": "assets/maps/lair/2f.png"},
        {"key": "roof", "name": "Roof", "image": "assets/maps/lair/roof.png"}
      ]'
      ;;
    nighthaven-labs)
      floors_json='[
        {"key": "b1", "name": "Basement", "image": "assets/maps/nighthaven-labs/b1.png"},
        {"key": "1f", "name": "First Floor", "image": "assets/maps/nighthaven-labs/1f.png"},
        {"key": "2f", "name": "Second Floor", "image": "assets/maps/nighthaven-labs/2f.png"},
        {"key": "roof", "name": "Roof", "image": "assets/maps/nighthaven-labs/roof.png"}
      ]'
      ;;
    close-quarter)
      floors_json='[
        {"key": "1f", "name": "First Floor", "image": "assets/maps/close-quarter/1f.png"},
        {"key": "2f", "name": "Second Floor", "image": "assets/maps/close-quarter/2f.png"}
      ]'
      ;;
    emerald-plains)
      floors_json='[
        {"key": "1f", "name": "First Floor", "image": "assets/maps/emerald-plains/1f.png"},
        {"key": "2f", "name": "Second Floor", "image": "assets/maps/emerald-plains/2f.png"},
        {"key": "roof", "name": "Roof", "image": "assets/maps/emerald-plains/roof.png"}
      ]'
      ;;
    coastline)
      floors_json='[
        {"key": "b1", "name": "Basement", "image": "assets/maps/coastline/b1.png"},
        {"key": "1f", "name": "First Floor", "image": "assets/maps/coastline/1f.png"},
        {"key": "2f", "name": "Second Floor", "image": "assets/maps/coastline/2f.png"}
      ]'
      ;;
    consulate)
      floors_json='[
        {"key": "b1", "name": "Basement", "image": "assets/maps/consulate/b1.png"},
        {"key": "1f", "name": "First Floor", "image": "assets/maps/consulate/1f.png"},
        {"key": "2f", "name": "Second Floor", "image": "assets/maps/consulate/2f.png"},
        {"key": "roof", "name": "Roof", "image": "assets/maps/consulate/roof.png"}
      ]'
      ;;
    favela)
      floors_json='[
        {"key": "b1", "name": "Basement", "image": "assets/maps/favela/b1.png"},
        {"key": "1f", "name": "First Floor", "image": "assets/maps/favela/1f.png"},
        {"key": "2f", "name": "Second Floor", "image": "assets/maps/favela/2f.png"},
        {"key": "roof", "name": "Roof", "image": "assets/maps/favela/roof.png"}
      ]'
      ;;
    fortress)
      floors_json='[
        {"key": "1f", "name": "First Floor", "image": "assets/maps/fortress/1f.png"},
        {"key": "2f", "name": "Second Floor", "image": "assets/maps/fortress/2f.png"},
        {"key": "roof", "name": "Roof", "image": "assets/maps/fortress/roof.png"}
      ]'
      ;;
    hereford-base)
      floors_json='[
        {"key": "b1", "name": "Basement", "image": "assets/maps/hereford-base/b1.png"},
        {"key": "1f", "name": "First Floor", "image": "assets/maps/hereford-base/1f.png"},
        {"key": "2f", "name": "Second Floor", "image": "assets/maps/hereford-base/2f.png"},
        {"key": "3f", "name": "Third Floor", "image": "assets/maps/hereford-base/3f.png"},
        {"key": "roof", "name": "Roof", "image": "assets/maps/hereford-base/roof.png"}
      ]'
      ;;
    house)
      floors_json='[
        {"key": "b1", "name": "Basement", "image": "assets/maps/house/b1.png"},
        {"key": "1f", "name": "First Floor", "image": "assets/maps/house/1f.png"},
        {"key": "2f", "name": "Second Floor", "image": "assets/maps/house/2f.png"}
      ]'
      ;;
    kanal)
      floors_json='[
        {"key": "b1", "name": "Basement", "image": "assets/maps/kanal/b1.png"},
        {"key": "1f", "name": "First Floor", "image": "assets/maps/kanal/1f.png"},
        {"key": "2f", "name": "Second Floor", "image": "assets/maps/kanal/2f.png"},
        {"key": "roof", "name": "Roof", "image": "assets/maps/kanal/roof.png"}
      ]'
      ;;
    oregon)
      floors_json='[
        {"key": "b1", "name": "Basement", "image": "assets/maps/oregon/b1.png"},
        {"key": "1f", "name": "First Floor", "image": "assets/maps/oregon/1f.png"},
        {"key": "2f", "name": "Second Floor", "image": "assets/maps/oregon/2f.png"},
        {"key": "roof", "name": "Roof", "image": "assets/maps/oregon/roof.png"}
      ]'
      ;;
    outback)
      floors_json='[
        {"key": "b1", "name": "Basement", "image": "assets/maps/outback/b1.png"},
        {"key": "1f", "name": "First Floor", "image": "assets/maps/outback/1f.png"},
        {"key": "2f", "name": "Second Floor", "image": "assets/maps/outback/2f.png"}
      ]'
      ;;
    presidential-plane)
      floors_json='[
        {"key": "1f", "name": "Level 1", "image": "assets/maps/presidential-plane/1f.png"},
        {"key": "2f", "name": "Level 2", "image": "assets/maps/presidential-plane/2f.png"},
        {"key": "3f", "name": "Level 3", "image": "assets/maps/presidential-plane/3f.png"},
        {"key": "roof", "name": "Roof", "image": "assets/maps/presidential-plane/roof.png"}
      ]'
      ;;
    skyscraper)
      floors_json='[
        {"key": "1f", "name": "First Floor", "image": "assets/maps/skyscraper/1f.png"},
        {"key": "2f", "name": "Second Floor", "image": "assets/maps/skyscraper/2f.png"},
        {"key": "roof", "name": "Roof", "image": "assets/maps/skyscraper/roof.png"}
      ]'
      ;;
    theme-park)
      floors_json='[
        {"key": "1f", "name": "First Floor", "image": "assets/maps/theme-park/1f.png"},
        {"key": "2f", "name": "Second Floor", "image": "assets/maps/theme-park/2f.png"},
        {"key": "roof", "name": "Roof", "image": "assets/maps/theme-park/roof.png"}
      ]'
      ;;
    tower)
      floors_json='[
        {"key": "1f", "name": "First Floor", "image": "assets/maps/tower/1f.png"},
        {"key": "2f", "name": "Second Floor", "image": "assets/maps/tower/2f.png"},
        {"key": "roof", "name": "Roof", "image": "assets/maps/tower/roof.png"}
      ]'
      ;;
    villa)
      floors_json='[
        {"key": "b1", "name": "Basement", "image": "assets/maps/villa/b1.png"},
        {"key": "1f", "name": "First Floor", "image": "assets/maps/villa/1f.png"},
        {"key": "2f", "name": "Second Floor", "image": "assets/maps/villa/2f.png"},
        {"key": "roof", "name": "Roof", "image": "assets/maps/villa/roof.png"}
      ]'
      ;;
    yacht)
      floors_json='[
        {"key": "b1", "name": "Basement", "image": "assets/maps/yacht/b1.png"},
        {"key": "1f", "name": "First Floor", "image": "assets/maps/yacht/1f.png"},
        {"key": "2f", "name": "Second Floor", "image": "assets/maps/yacht/2f.png"},
        {"key": "roof", "name": "Roof", "image": "assets/maps/yacht/roof.png"}
      ]'
      ;;
  esac
  
  cat > "$map_dir/map.json" << EOF
{
  "key": "$map_key",
  "name": "$map_name",
  "floors": $floors_json,
  "size": {
    "width": 0,
    "height": 0
  },
  "calibration": {
    "origin": { "x": 0, "y": 0 },
    "scale": 1.0
  },
  "layers": {
    "walls": [],
    "doors": [],
    "windows": [],
    "hatches": [],
    "stairs": [],
    "sites": [],
    "spawn_points": [],
    "cameras": [],
    "gadgets": []
  },
  "notes": ""
}
EOF
}

# Create map.json for each map
create_map_json "bank" "银行" "/home/node/clawd/little-herta/assets/maps/bank" 4
create_map_json "chalet" "木屋" "/home/node/clawd/little-herta/assets/maps/chalet" 4
create_map_json "kafe-dostoyevsky" "杜斯妥也夫斯基咖啡馆" "/home/node/clawd/little-herta/assets/maps/kafe-dostoyevsky" 4
create_map_json "border" "边境" "/home/node/clawd/little-herta/assets/maps/border" 3
create_map_json "clubhouse" "俱乐部会所" "/home/node/clawd/little-herta/assets/maps/clubhouse" 4
create_map_json "stadium-alpha" "A号竞技场" "/home/node/clawd/little-herta/assets/maps/stadium-alpha" 5
create_map_json "stadium-bravo" "B号竞技场" "/home/node/clawd/little-herta/assets/maps/stadium-bravo" 4
create_map_json "lair" "虎穴狼巢" "/home/node/clawd/little-herta/assets/maps/lair" 4
create_map_json "nighthaven-labs" "永夜安港实验室" "/home/node/clawd/little-herta/assets/maps/nighthaven-labs" 4
create_map_json "close-quarter" "近距离战斗" "/home/node/clawd/little-herta/assets/maps/close-quarter" 2
create_map_json "emerald-plains" "翡翠原" "/home/node/clawd/little-herta/assets/maps/emerald-plains" 3
create_map_json "coastline" "海岸线" "/home/node/clawd/little-herta/assets/maps/coastline" 3
create_map_json "consulate" "领事馆" "/home/node/clawd/little-herta/assets/maps/consulate" 4
create_map_json "favela" "贫民窟" "/home/node/clawd/little-herta/assets/maps/favela" 4
create_map_json "fortress" "要塞" "/home/node/clawd/little-herta/assets/maps/fortress" 3
create_map_json "hereford-base" "赫里福基地" "/home/node/clawd/little-herta/assets/maps/hereford-base" 5
create_map_json "house" "芝加哥豪宅" "/home/node/clawd/little-herta/assets/maps/house" 3
create_map_json "kanal" "运河" "/home/node/clawd/little-herta/assets/maps/kanal" 4
create_map_json "oregon" "俄勒冈乡间屋宅" "/home/node/clawd/little-herta/assets/maps/oregon" 4
create_map_json "outback" "荒漠服务站" "/home/node/clawd/little-herta/assets/maps/outback" 3
create_map_json "presidential-plane" "总统专机" "/home/node/clawd/little-herta/assets/maps/presidential-plane" 4
create_map_json "skyscraper" "摩天大楼" "/home/node/clawd/little-herta/assets/maps/skyscraper" 3
create_map_json "theme-park" "主题公园" "/home/node/clawd/little-herta/assets/maps/theme-park" 3
create_map_json "tower" "塔楼" "/home/node/clawd/little-herta/assets/maps/tower" 3
create_map_json "villa" "庄园" "/home/node/clawd/little-herta/assets/maps/villa" 4
create_map_json "yacht" "游艇" "/home/node/clawd/little-herta/assets/maps/yacht" 4

echo "All map.json files created!"