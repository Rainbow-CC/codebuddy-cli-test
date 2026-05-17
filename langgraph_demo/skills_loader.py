import os
from pathlib import Path

def load_local_skills(root_dir: str):
    """
    扫描目录下的 SKILL.md 文件并提取指令。
    类似 CodeBuddy 的技能发现机制。
    """
    instructions = []
    root_path = Path(root_dir)
    
    # 查找所有子目录下的 SKILL.md
    for skill_file in root_path.glob("**/SKILL.md"):
        try:
            with open(skill_file, "r", encoding="utf-8") as f:
                content = f.read()
                skill_name = skill_file.parent.name
                instructions.append(f"### Skill: {skill_name}\n{content}")
        except Exception as e:
            print(f"警告: 无法读取技能文件 {skill_file}: {e}")
            
    return "\n\n".join(instructions)
