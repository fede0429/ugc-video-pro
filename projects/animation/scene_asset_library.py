
from __future__ import annotations

from dataclasses import dataclass, asdict, field

from .models import StoryBible, EpisodePlan


@dataclass
class SceneAsset:
    asset_id: str
    asset_type: str
    label: str
    prompt_anchor: str
    reusable: bool = True
    continuity_rules: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


class SceneAssetLibrary:
    def __init__(self):
        self.default_assets = [
            SceneAsset("penthouse_window", "location", "落地窗豪宅客厅", "luxury penthouse interior, floor-to-ceiling windows, cool moonlight", True, ["窗景和冷色主光保持一致", "家具布局不要随机变化"]),
            SceneAsset("office_desk", "prop", "办公桌与电脑", "clean office desk, laptop, scattered script pages, city-night ambience", True, ["桌面物件保留连续性"]),
            SceneAsset("contract_folder", "prop", "合同文件夹", "black contract folder with metallic clip, close-up friendly", True, ["文件夹外观不能漂移"]),
            SceneAsset("elevator_hall", "location", "电梯厅", "luxury elevator hall, reflective marble floor, sharp overhead lights", True, ["地砖纹理与色调保持一致"]),
            SceneAsset("phone_chat", "ui", "聊天记录手机界面", "phone screen with dramatic unread messages, elegant UI, crisp typography", False, ["UI 排版要统一"]),
        ]

    def build_for_story(self, story_bible: StoryBible) -> list[dict]:
        assets = [a.to_dict() for a in self.default_assets]
        assets.append(SceneAsset(
            asset_id="genre_anchor",
            asset_type="style",
            label=f"{story_bible.genre}视觉锚点",
            prompt_anchor=f"{story_bible.visual_style}, {story_bible.tone}, recurring cinematic identity",
            reusable=True,
            continuity_rules=["全剧维持相同风格浓度和镜头质感"],
        ).to_dict())
        return assets

    def assign_to_episode(self, episode: EpisodePlan, assets: list[dict]) -> dict[str, list[dict]]:
        mapping: dict[str, list[dict]] = {}
        for scene in episode.scenes:
            picks = [assets[0], assets[2], assets[-1]]
            if "办公室" in scene.location or "办公" in scene.location:
                picks = [assets[1], assets[2], assets[-1]]
            elif "电梯" in scene.location:
                picks = [assets[3], assets[4], assets[-1]]
            mapping[scene.scene_id] = picks
            for shot in scene.shots:
                for asset in picks:
                    shot.continuity_notes.append(f"scene_asset:{asset['asset_id']}:{asset['label']}")
                    if asset.get("prompt_anchor"):
                        shot.continuity_notes.append(f"asset_anchor:{asset['prompt_anchor']}")
        return mapping
