from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from phrase_taxonomy_skill.taxonomy import (
    TaxonomyNode,
    build_compact_rows,
    build_compression_audit,
    build_core_nodes,
    build_equivalence_groups,
    build_mermaid_taxonomy,
    compress_taxonomy_depth,
    guess_layer,
    is_incomplete_phrase,
    load_phrase_input,
    rank_parent_candidates,
    resolve_cycle_groups,
    stage1_rule_classify,
)


class TaxonomySkillTests(unittest.TestCase):
    def test_load_phrase_input_supports_strings_dicts_and_dedupes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "phrases.json"
            payload = {
                "task_id": "demo-case",
                "phrases": [
                    "未佩戴安全带",
                    {"id": "p2", "text": "监管缺失"},
                    {"text": "未佩戴安全带"},
                ],
            }
            input_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

            result = load_phrase_input(input_path)

        self.assertEqual(result["task_id"], "demo-case")
        self.assertEqual([item["text"] for item in result["phrases"]], ["未佩戴安全带", "监管缺失"])
        self.assertEqual(result["phrases"][0]["id"], "p1")
        self.assertEqual(result["phrases"][1]["id"], "p2")

    def test_stage1_rule_classify_excludes_measure_like_phrases(self) -> None:
        result = stage1_rule_classify("加强现场监督管理")
        self.assertFalse(result["in_taxonomy"])
        self.assertEqual(result["decision_source"], "rule")

    def test_stage1_rule_classify_keeps_negated_cause_like_phrases_for_llm(self) -> None:
        result = stage1_rule_classify("未开展安全教育培训")
        self.assertIsNone(result["in_taxonomy"])
        self.assertEqual(result["decision_source"], "llm")

    def test_stage1_rule_classify_excludes_enforcement_and_measure_phrases(self) -> None:
        result = stage1_rule_classify("依法查处违规行为")
        self.assertFalse(result["in_taxonomy"])
        self.assertEqual(result["decision_source"], "rule")

    def test_stage1_rule_classify_excludes_incomplete_fragment(self) -> None:
        result = stage1_rule_classify("未明确")
        self.assertFalse(result["in_taxonomy"])
        self.assertEqual(result["decision_source"], "rule")

    def test_stage1_rule_classify_keeps_complete_behavior_phrase(self) -> None:
        result = stage1_rule_classify("未戴安全帽")
        self.assertIsNone(result["in_taxonomy"])
        self.assertEqual(result["decision_source"], "llm")

    def test_stage1_rule_classify_excludes_management_action_phrase(self) -> None:
        result = stage1_rule_classify("未明确安全责任人")
        self.assertFalse(result["in_taxonomy"])
        self.assertEqual(result["decision_source"], "rule")

    def test_stage1_rule_classify_excludes_management_action_phrase_for_policy(self) -> None:
        result = stage1_rule_classify("未落实安全制度")
        self.assertFalse(result["in_taxonomy"])
        self.assertEqual(result["decision_source"], "rule")

    def test_is_incomplete_phrase_detects_obvious_fragment(self) -> None:
        self.assertTrue(is_incomplete_phrase("未明确"))
        self.assertFalse(is_incomplete_phrase("未明确吊装指挥人员"))

    def test_guess_layer_prefers_environment_for_lighting_phrase(self) -> None:
        layer, _ = guess_layer("作业环境照明不足")
        self.assertEqual(layer, "环")

    def test_guess_layer_prefers_environment_for_weather_and_lighting(self) -> None:
        layer, _ = guess_layer("夜间作业照度不足")
        self.assertEqual(layer, "环")

    def test_guess_layer_treats_supervision_phrase_as_management(self) -> None:
        layer, _ = guess_layer("未监督佩戴安全防护用品")
        self.assertEqual(layer, "管")

    def test_guess_layer_keeps_direct_ppe_violation_as_human(self) -> None:
        layer, _ = guess_layer("未佩戴安全防护用品")
        self.assertEqual(layer, "人")

    def test_guess_layer_treats_driver_behavior_as_human(self) -> None:
        layer, _ = guess_layer("驾驶员疏忽大意，未遵守行车规范")
        self.assertEqual(layer, "人")

    def test_guess_layer_treats_blind_spot_observation_as_human(self) -> None:
        layer, _ = guess_layer("倒车时未观察盲区")
        self.assertEqual(layer, "人")

    def test_rank_parent_candidates_prefers_same_layer_and_more_general_parent(self) -> None:
        child = TaxonomyNode(
            id="c1",
            text="未佩戴安全带",
            in_taxonomy=True,
            layer="人",
            granularity_level=3,
        )
        candidates = [
            TaxonomyNode(
                id="p1",
                text="未佩戴安全防护用品",
                in_taxonomy=True,
                layer="人",
                granularity_level=2,
            ),
            TaxonomyNode(
                id="p2",
                text="监管缺失",
                in_taxonomy=True,
                layer="管",
                granularity_level=2,
            ),
            TaxonomyNode(
                id="p3",
                text="人的不安全行为",
                in_taxonomy=True,
                layer="人",
                granularity_level=1,
            ),
        ]

        ranked = rank_parent_candidates(child, candidates, max_candidates=3)

        self.assertEqual([item["parent_id"] for item in ranked], ["p1", "p3"])

    def test_rank_parent_candidates_rejects_longer_more_specific_phrase(self) -> None:
        child = TaxonomyNode(
            id="c1",
            text="未佩戴安全带",
            in_taxonomy=True,
            layer="人",
            granularity_level=4,
        )
        candidates = [
            TaxonomyNode(
                id="p1",
                text="未佩戴安全带作业",
                in_taxonomy=True,
                layer="人",
                granularity_level=4,
            ),
            TaxonomyNode(
                id="p2",
                text="未佩戴安全防护用品",
                in_taxonomy=True,
                layer="人",
                granularity_level=3,
            ),
        ]

        ranked = rank_parent_candidates(child, candidates, max_candidates=3)

        self.assertEqual([item["parent_id"] for item in ranked], ["p2"])

    def test_rank_parent_candidates_prefers_general_protection_parent_over_scene_specific_peer(self) -> None:
        child = TaxonomyNode(
            id="c1",
            text="电缆随意拉接无防护",
            in_taxonomy=True,
            layer="物",
            granularity_level=5,
        )
        candidates = [
            TaxonomyNode(
                id="p1",
                text="未设置安全防护设施",
                in_taxonomy=True,
                layer="物",
                granularity_level=4,
            ),
            TaxonomyNode(
                id="p2",
                text="临边作业无防护设施",
                in_taxonomy=True,
                layer="物",
                granularity_level=5,
            ),
        ]

        ranked = rank_parent_candidates(child, candidates, max_candidates=3)

        self.assertEqual([item["parent_id"] for item in ranked], ["p1"])

    def test_build_equivalence_groups_clusters_pure_rewrites(self) -> None:
        nodes = [
            TaxonomyNode(id="p1", text="安全培训不足", in_taxonomy=True, layer="管", granularity_level=2),
            TaxonomyNode(id="p2", text="安全培训不到位", in_taxonomy=True, layer="管", granularity_level=2),
            TaxonomyNode(id="p3", text="未佩戴安全带", in_taxonomy=True, layer="人", granularity_level=4),
        ]

        groups, member_to_group = build_equivalence_groups(nodes)

        self.assertEqual(len(groups), 1)
        self.assertEqual(set(member_to_group), {"p1", "p2"})
        self.assertTrue(groups[0].text.startswith("归并节点："))

    def test_build_equivalence_groups_clusters_subject_variants(self) -> None:
        nodes = [
            TaxonomyNode(id="p1", text="主要负责人未履行安全管理职责", in_taxonomy=True, layer="管", granularity_level=4),
            TaxonomyNode(id="p2", text="企业主要负责人未履行安全管理职责", in_taxonomy=True, layer="管", granularity_level=4),
            TaxonomyNode(id="p3", text="企业负责人未履行安全管理职责", in_taxonomy=True, layer="管", granularity_level=4),
        ]

        groups, member_to_group = build_equivalence_groups(nodes)

        self.assertEqual(len(groups), 1)
        self.assertEqual(set(member_to_group), {"p1", "p2", "p3"})

    def test_build_core_nodes_creates_formal_core_for_shared_protection_theme(self) -> None:
        phrase_nodes = [
            TaxonomyNode(id="p1", text="临边作业无防护设施", in_taxonomy=True, layer="物", granularity_level=5),
            TaxonomyNode(id="p2", text="电缆随意拉接无防护", in_taxonomy=True, layer="物", granularity_level=5),
            TaxonomyNode(id="p3", text="未设置安全防护设施", in_taxonomy=True, layer="物", granularity_level=4),
        ]

        core_nodes, target_to_core = build_core_nodes(phrase_nodes, [], {})

        self.assertEqual(len(core_nodes), 1)
        self.assertEqual(core_nodes[0].text, "防护措施缺失")
        self.assertEqual(target_to_core, {"p1": core_nodes[0].id, "p2": core_nodes[0].id, "p3": core_nodes[0].id})

    def test_build_core_nodes_does_not_promote_uncontrolled_generic_subject(self) -> None:
        phrase_nodes = [
            TaxonomyNode(id="p1", text="建设单位监管不到位", in_taxonomy=True, layer="管", granularity_level=3),
            TaxonomyNode(id="p2", text="房东监管不到位", in_taxonomy=True, layer="管", granularity_level=3),
        ]

        core_nodes, target_to_core = build_core_nodes(phrase_nodes, [], {})

        self.assertEqual(core_nodes, [])
        self.assertEqual(target_to_core, {})

    def test_build_core_nodes_creates_policy_core_for_rule_and_system_phrases(self) -> None:
        phrase_nodes = [
            TaxonomyNode(id="p1", text="外包管理制度缺失", in_taxonomy=True, layer="管", granularity_level=2),
            TaxonomyNode(id="p2", text="消防安全管理制度缺失", in_taxonomy=True, layer="管", granularity_level=3),
            TaxonomyNode(id="p3", text="未严格执行安全管理制度", in_taxonomy=True, layer="管", granularity_level=3),
            TaxonomyNode(id="p4", text="未严格执行安全规定", in_taxonomy=True, layer="管", granularity_level=5),
        ]

        core_nodes, target_to_core = build_core_nodes(phrase_nodes, [], {})

        self.assertEqual(len(core_nodes), 1)
        self.assertEqual(core_nodes[0].text, "制度问题")
        self.assertEqual(target_to_core, {"p1": core_nodes[0].id, "p2": core_nodes[0].id, "p3": core_nodes[0].id, "p4": core_nodes[0].id})

    def test_build_core_nodes_expands_policy_core_to_management_missing(self) -> None:
        phrase_nodes = [
            TaxonomyNode(id="p1", text="施工管理缺失", in_taxonomy=True, layer="管", granularity_level=2),
            TaxonomyNode(id="p2", text="外包管理制度缺失", in_taxonomy=True, layer="管", granularity_level=2),
            TaxonomyNode(id="p3", text="消防安全管理制度缺失", in_taxonomy=True, layer="管", granularity_level=3),
        ]

        core_nodes, target_to_core = build_core_nodes(phrase_nodes, [], {})

        self.assertEqual(len(core_nodes), 1)
        self.assertEqual(core_nodes[0].text, "制度问题")
        self.assertEqual(set(target_to_core), {"p1", "p2", "p3"})

    def test_build_core_nodes_creates_duty_core_for_subject_variants(self) -> None:
        phrase_nodes = [
            TaxonomyNode(id="p1", text="房东未履行安全管理职责", in_taxonomy=True, layer="管", granularity_level=3),
            TaxonomyNode(id="p2", text="建设单位未履行安全管理职责", in_taxonomy=True, layer="管", granularity_level=3),
            TaxonomyNode(id="p3", text="监理单位未履行安全监管职责", in_taxonomy=True, layer="管", granularity_level=3),
        ]

        core_nodes, target_to_core = build_core_nodes(phrase_nodes, [], {})

        self.assertEqual(len(core_nodes), 1)
        self.assertEqual(core_nodes[0].text, "职责履行不到位")
        self.assertEqual(set(target_to_core), {"p1", "p2", "p3"})

    def test_build_core_nodes_avoids_duplicate_core_label_across_layers(self) -> None:
        phrase_nodes = [
            TaxonomyNode(id="p1", text="临边作业无防护设施", in_taxonomy=True, layer="物", granularity_level=5),
            TaxonomyNode(id="p2", text="未监督佩戴劳动防护用品", in_taxonomy=True, layer="管", granularity_level=3),
        ]

        core_nodes, _ = build_core_nodes(phrase_nodes, [], {})

        self.assertEqual([node.text for node in core_nodes], [])

    def test_resolve_cycle_groups_replaces_mutual_links_with_group_parent(self) -> None:
        nodes = [
            {
                "id": "p1",
                "text": "安全培训不足",
                "stage1_in_taxonomy": True,
                "stage2_layer": "管",
                "stage3_granularity_level": 2,
                "node_kind": "phrase",
            },
            {
                "id": "p2",
                "text": "安全培训不到位",
                "stage1_in_taxonomy": True,
                "stage2_layer": "管",
                "stage3_granularity_level": 2,
                "node_kind": "phrase",
            },
        ]
        edges = [
            {"child_id": "p1", "parent_id": "p2", "relation": "is_a_more_specific_cause_of"},
            {"child_id": "p2", "parent_id": "p1", "relation": "is_a_more_specific_cause_of"},
        ]

        new_nodes, new_edges = resolve_cycle_groups(nodes, edges)

        group_nodes = [node for node in new_nodes if node["node_kind"] == "group"]
        self.assertEqual(len(group_nodes), 1)
        self.assertEqual(len(new_edges), 2)
        self.assertEqual({edge["parent_id"] for edge in new_edges}, {group_nodes[0]["id"]})

    def test_build_compact_rows_includes_parent_text_and_root_flag(self) -> None:
        nodes = [
            {
                "id": "p1",
                "text": "未佩戴安全防护用品",
                "stage1_in_taxonomy": True,
                "stage2_layer": "人",
                "stage3_granularity_level": 2,
            },
            {
                "id": "p2",
                "text": "未佩戴安全带",
                "stage1_in_taxonomy": True,
                "stage2_layer": "人",
                "stage3_granularity_level": 4,
            },
        ]
        edges = [{"child_id": "p2", "parent_id": "p1", "relation": "is_a_more_specific_cause_of"}]

        compact = build_compact_rows(nodes, edges)

        self.assertEqual(
            compact,
            [
                {
                    "id": "p1",
                    "text": "未佩戴安全防护用品",
                    "parent_id": None,
                    "parent_text": None,
                    "layer": "人",
                    "granularity_level": 2,
                    "is_root": True,
                    "node_kind": "phrase",
                },
                {
                    "id": "p2",
                    "text": "未佩戴安全带",
                    "parent_id": "p1",
                    "parent_text": "未佩戴安全防护用品",
                    "layer": "人",
                    "granularity_level": 4,
                    "is_root": False,
                    "node_kind": "phrase",
                },
            ],
        )

    def test_build_compact_rows_hides_internal_group_nodes(self) -> None:
        nodes = [
            {
                "id": "eq1",
                "text": "归并节点：未佩戴安全防护用品",
                "stage1_in_taxonomy": True,
                "stage2_layer": "人",
                "stage3_granularity_level": 3,
                "node_kind": "group",
            },
            {
                "id": "p1",
                "text": "未佩戴安全防护用品",
                "stage1_in_taxonomy": True,
                "stage2_layer": "人",
                "stage3_granularity_level": 3,
                "node_kind": "phrase",
            },
            {
                "id": "p2",
                "text": "未佩戴安全带",
                "stage1_in_taxonomy": True,
                "stage2_layer": "人",
                "stage3_granularity_level": 4,
                "node_kind": "phrase",
            },
        ]
        edges = [
            {"child_id": "p1", "parent_id": "eq1", "relation": "equivalent_variant_of"},
            {"child_id": "p2", "parent_id": "eq1", "relation": "is_a_more_specific_cause_of"},
        ]

        compact = build_compact_rows(nodes, edges)

        self.assertEqual([row["id"] for row in compact], ["p1", "p2"])
        self.assertIsNone(compact[0]["parent_id"])
        self.assertIsNone(compact[1]["parent_id"])

    def test_build_compact_rows_keeps_core_nodes_visible(self) -> None:
        nodes = [
            {
                "id": "core1",
                "text": "防护措施缺失",
                "stage1_in_taxonomy": True,
                "stage2_layer": "物",
                "stage3_granularity_level": 3,
                "node_kind": "core",
            },
            {
                "id": "eq1",
                "text": "归并节点：无防护设施",
                "stage1_in_taxonomy": True,
                "stage2_layer": "物",
                "stage3_granularity_level": 4,
                "node_kind": "group",
            },
            {
                "id": "p1",
                "text": "临边作业无防护设施",
                "stage1_in_taxonomy": True,
                "stage2_layer": "物",
                "stage3_granularity_level": 5,
                "node_kind": "phrase",
            },
        ]
        edges = [
            {"child_id": "eq1", "parent_id": "core1", "relation": "is_context_specific_variant_of"},
            {"child_id": "p1", "parent_id": "eq1", "relation": "equivalent_variant_of"},
        ]

        compact = build_compact_rows(nodes, edges)

        self.assertEqual([row["id"] for row in compact], ["core1", "p1"])
        self.assertIsNone(compact[0]["parent_id"])
        self.assertEqual(compact[1]["parent_id"], "core1")
        self.assertEqual(compact[1]["parent_text"], "防护措施缺失")

    def test_build_compression_audit_tracks_original_and_compressed_targets(self) -> None:
        nodes = [
            {
                "id": "core1",
                "text": "防护措施缺失",
                "stage1_in_taxonomy": True,
                "stage2_layer": "物",
                "stage3_granularity_level": 2,
                "node_kind": "core",
            },
            {
                "id": "eq1",
                "text": "归并节点：无防护设施",
                "stage1_in_taxonomy": True,
                "stage2_layer": "物",
                "stage3_granularity_level": 4,
                "node_kind": "group",
            },
            {
                "id": "p1",
                "text": "临边作业无防护设施",
                "stage1_in_taxonomy": True,
                "stage2_layer": "物",
                "stage3_granularity_level": 5,
                "node_kind": "phrase",
            },
        ]
        edges = [
            {"child_id": "eq1", "parent_id": "core1", "relation": "is_context_specific_variant_of"},
            {"child_id": "p1", "parent_id": "eq1", "relation": "equivalent_variant_of"},
        ]

        audit = build_compression_audit(nodes, edges)

        self.assertEqual(
            audit,
            [
                {
                    "phrase_id": "p1",
                    "original_text": "临边作业无防护设施",
                    "group_id": "eq1",
                    "group_text": "归并节点：无防护设施",
                    "core_id": "core1",
                    "core_text": "防护措施缺失",
                    "visible_parent_id": "core1",
                    "visible_parent_text": "防护措施缺失",
                }
            ],
        )

    def test_build_mermaid_taxonomy_outputs_parent_child_edges(self) -> None:
        compact = [
            {
                "id": "p1",
                "text": "未佩戴安全防护用品",
                "parent_id": None,
                "parent_text": None,
                "layer": "人",
                "granularity_level": 2,
                "is_root": True,
            },
            {
                "id": "p2",
                "text": "未佩戴安全带",
                "parent_id": "p1",
                "parent_text": "未佩戴安全防护用品",
                "layer": "人",
                "granularity_level": 4,
                "is_root": False,
            },
        ]

        mermaid = build_mermaid_taxonomy(compact)

        self.assertIn("flowchart TD", mermaid)
        self.assertIn('p1["未佩戴安全防护用品', mermaid)
        self.assertIn("p1 --> p2", mermaid)

    def test_compress_taxonomy_depth_limits_tree_to_six_levels(self) -> None:
        nodes = [
            {
                "id": f"p{i}",
                "text": f"node-{i}",
                "stage1_in_taxonomy": True,
                "stage2_layer": "管",
                "stage3_granularity_level": min(i, 5),
                "node_kind": "phrase" if i == 1 else ("group" if i in (2, 3) else "phrase"),
            }
            for i in range(1, 9)
        ]
        edges = [
            {"child_id": "p2", "parent_id": "p1", "relation": "is_a_more_specific_cause_of"},
            {"child_id": "p3", "parent_id": "p2", "relation": "is_a_more_specific_cause_of"},
            {"child_id": "p4", "parent_id": "p3", "relation": "is_a_more_specific_cause_of"},
            {"child_id": "p5", "parent_id": "p4", "relation": "is_a_more_specific_cause_of"},
            {"child_id": "p6", "parent_id": "p5", "relation": "is_a_more_specific_cause_of"},
            {"child_id": "p7", "parent_id": "p6", "relation": "is_a_more_specific_cause_of"},
            {"child_id": "p8", "parent_id": "p7", "relation": "is_a_more_specific_cause_of"},
        ]

        compressed = compress_taxonomy_depth(nodes, edges, max_depth=6)
        parent_by_child = {edge["child_id"]: edge["parent_id"] for edge in compressed}

        depth = 1
        current = "p8"
        while current in parent_by_child:
            current = parent_by_child[current]
            depth += 1

        self.assertLessEqual(depth, 6)
        self.assertNotEqual(parent_by_child["p3"], "p2")


if __name__ == "__main__":
    unittest.main()
