  mkdir -p media_properties
  count=0
  total=$(find media_pdfs -name "*_composition.json" | wc -l)

  for file in media_pdfs/*_composition.json; do
      ((count++))
      echo "Processing $count/$total: $(basename "$file")"
      python src/scripts/compute_media_properties.py "$file" -o "media_properties/$(basename "$file" .json)_properties.json"
  done
