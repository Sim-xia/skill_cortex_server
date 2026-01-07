# Configuration Files / 配置文件

This directory contains configuration files for the Skill-Cortex import system.

## Examples / 示例

The `examples/` directory contains sample configuration files:

- `skills-config.yaml` - YAML format configuration example
- `skills-config.json` - JSON format configuration example

## Usage / 使用方法

1. Copy an example file to your project root or desired location
2. Modify the repository list and settings as needed
3. Use with the import script:

```bash
# Use config file in current directory (auto-detected)
python import_skills.py --dry-run

# Use specific config file
python import_skills.py --config path/to/your-config.yaml
```

## Configuration Format / 配置格式

### Repositories / 仓库配置

Each repository entry supports:
- `name`: Unique identifier for the repository
- `url`: Git repository URL
- `enabled`: Whether to include this repository (true/false)
- `branch`: Optional specific branch to use

### Settings / 设置

Future settings for advanced features:
- `incremental`: Enable incremental imports (planned feature)
- `validation`: Enable skill validation (planned feature)

## Auto-discovery / 自动发现

The import script automatically looks for these files in the current directory:
1. `skills-config.yaml`
2. `skills-config.yml` 
3. `skills-config.json`

If none are found, it uses the default repository list.