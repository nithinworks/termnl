echo "Uninstalling termnl..."

rm -rf "$HOME/.termnl"
rm -f "$HOME/.local/bin/termnl"

# Remove termnl lines from shell configs
for rc_file in "$HOME/.zprofile" "$HOME/.zshrc" "$HOME/.bashrc" "$HOME/.bash_profile"; do
    if [ -f "$rc_file" ]; then
        # Remove auto-launch line and its comment
        sed -i '' '/termnl # auto-launch/d' "$rc_file" 2>/dev/null || sed -i '/termnl # auto-launch/d' "$rc_file" 2>/dev/null
        sed -i '' '/termnl - auto-launch/d' "$rc_file" 2>/dev/null || sed -i '/termnl - auto-launch/d' "$rc_file" 2>/dev/null
        # Remove PATH configuration
        sed -i '' '/termnl - PATH/d' "$rc_file" 2>/dev/null || sed -i '/termnl - PATH/d' "$rc_file" 2>/dev/null
    fi
done

echo "✓ termnl has been removed"