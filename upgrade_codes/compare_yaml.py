from ruamel.yaml import YAML

conf1 = "conf.yaml"
conf2 = "config_templates/conf.default.yaml"


def collect_all_key_paths(d, prefix=""):
    keys = set()
    for k, v in d.items():
        full_key = f"{prefix}.{k}" if prefix else k
        keys.add(full_key)
        if isinstance(v, dict):
            keys.update(collect_all_key_paths(v, full_key))
    return keys


def collect_leaf_key_paths(d, prefix=""):
    keys = set()
    for k, v in d.items():
        full_key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            keys.update(collect_leaf_key_paths(v, full_key))
        else:
            keys.add(full_key)
    return keys


def get_value_by_path(d, path_str):
    keys = path_str.split(".")
    current = d
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return None
    return current


def compare_yaml_keys(dict1, dict2):
    keys1 = collect_all_key_paths(dict1)
    keys2 = collect_all_key_paths(dict2)
    only_in_1 = keys1 - keys2
    only_in_2 = keys2 - keys1
    return only_in_1, only_in_2


def compare_yaml_values(dict1, dict2):
    leaf_keys1 = collect_leaf_key_paths(dict1)
    leaf_keys2 = collect_leaf_key_paths(dict2)
    common_leaf_keys = leaf_keys1 & leaf_keys2

    differences = []

    for key in sorted(common_leaf_keys):
        value1 = get_value_by_path(dict1, key)
        value2 = get_value_by_path(dict2, key)

        if value1 != value2:
            differences.append({"key_path": key, "value1": value1, "value2": value2})

    if not differences:
        print("All common leaf values are identical\n")
    else:
        print(f"Found {len(differences)} differing field(s):\n\n")
        for diff in differences:
            print(f"Key path: {diff['key_path']}\n")
            print(f"  Value in {conf1}: {diff['value1']}\n")
            print(f"  Value in {conf2}: {diff['value2']}\n")
            print("-" * 50 + "\n")

    return differences


if __name__ == "__main__":
    yaml = YAML(typ="safe")
    with (
        open(conf1, "r", encoding="utf-8") as f1,
        open(conf2, "r", encoding="utf-8") as f2,
    ):
        config1 = yaml.load(f1)
        config2 = yaml.load(f2)

    # Compare differences in keys.
    only_in_1, only_in_2 = compare_yaml_keys(config1, config2)

    if not only_in_1 and not only_in_2:
        print("All YAML keys are identical")
    else:
        print("Keys differ:")
        if only_in_1:
            print(f"Only in {conf1} ({len(only_in_1)} key(s)):")
            for key in sorted(only_in_1):
                print(f"  - {key}")
        if only_in_2:
            print(f"\nOnly in {conf2} ({len(only_in_2)} key(s)):")
            for key in sorted(only_in_2):
                print(f"  - {key}")

    # Compare differences in values.
    diff_count = compare_yaml_values(config1, config2)
