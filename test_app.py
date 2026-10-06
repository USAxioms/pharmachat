"""Tests for the corrected engine and app. Run: python3 test_app.py"""
import json, os, unittest
os.environ.pop("ANTHROPIC_API_KEY", None)
import engine, app

TREM2 = [{"role": "user", "content": "Run the ledger for TREM2"}]

class Engine(unittest.TestCase):
    def setUp(self):
        self.p = engine.run_discovery(engine.PRESET_TARGETS["trem2"])
    def test_seal_verifies(self):
        self.assertTrue(engine.verify_payload(self.p))
    def test_tamper_detected(self):
        self.p["content"]["status"]["superintelligence_criteria_met"] = True
        self.assertFalse(engine.verify_payload(self.p))
    def test_unmeasured_criteria_never_met(self):
        c = self.p["content"]["criteria"]
        for k in ("compton_safety", "performance_velocity"):
            self.assertFalse(c[k]["measured"]); self.assertFalse(c[k]["met"])
    def test_steps_carry_full_reasoning(self):
        for pw in self.p["content"]["pathways"].values():
            for st in pw["steps"]:
                for k in ("transformation", "input_state", "output_state", "grounding_axioms", "ontological_trace"):
                    self.assertIn(k, st)
    def test_candidate_from_generated_scaffold(self):
        cand = next(iter(self.p["content"]["candidates"].values()))
        self.assertEqual(cand["novelty_score"], 0.78)
        self.assertEqual(cand["value_provenance"]["smiles"], "placeholder")
    def test_missing_target_fields_rejected(self):
        with self.assertRaises(ValueError):
            engine.target_from_dict({"target_name": "X"})
    def test_no_numpy(self):
        self.assertNotIn("numpy", open(engine.__file__, encoding="utf-8").read())

class Lambda(unittest.TestCase):
    def setUp(self):
        p = engine.run_discovery(engine.PRESET_TARGETS["trem2"])
        self.a = next(iter(p["content"]["assessments"].values()))
    def test_lambda_no_longer_zero(self):
        self.assertGreater(self.a["lambda"]["strict"]["lambda_total"], 0)
        self.assertGreater(self.a["lambda"]["strict"]["components"]["U_Sub"], 0)
    def test_feature_extraction_reads_objects(self):
        lam = engine.LambdaOptimizationEngine()
        t = engine.target_from_dict(engine.PRESET_TARGETS["trem2"])
        self.assertIn("disease", lam._extract_features_deep({"target": t}))
    def test_original_mode_preserved_and_visible(self):
        self.assertAlmostEqual(self.a["lambda"]["original_over_strict"], 2.0, places=6)
        self.assertTrue(any("50% cost cut" in e for e in self.a["lambda"]["original"]["events"]))
        self.assertFalse(any("cost cut" in e for e in self.a["lambda"]["strict"]["events"]))
    def test_strict_never_promotes(self):
        lam = engine.LambdaOptimizationEngine(strict=True)
        self.assertLess(lam.compute_decision_accuracy(0.62, [0.7], True, 0.95), 0.75)
        orig = engine.LambdaOptimizationEngine(strict=False)
        self.assertEqual(orig.compute_decision_accuracy(0.62, [0.7], True, 0.95), 0.75)
    def test_strict_never_rewrites_inputs(self):
        lam = engine.LambdaOptimizationEngine(strict=True)
        m = engine.LambdaMetrics(0.5, 2.0, 0.8, 0.5, 0.5, 0.0)
        state = {"novelty_score": 0.5, "development_timeline_months": 60}
        self.assertEqual(lam._apply_refinement_suggestions(state, [], m), state)
    def test_risk_flags_and_confidence(self):
        self.assertTrue(any(f["severity"] == "high" for f in self.a["risk_flags"]))
        self.assertGreater(self.a["confidence"]["value"], 0)

class App(unittest.TestCase):
    def test_every_answer_ends_with_confidence_and_risk(self):
        r = app.handle_chat({"messages": TREM2})
        self.assertIn("**Confidence and risk**", r["reply"])
        self.assertIn("not a measured risk", r["reply"])
        self.assertEqual(set(r["verdict"]["assessment"]["risk"]), {"high", "medium", "low"})
    def test_new_run(self):
        r = app.handle_chat({"messages": TREM2})
        self.assertEqual(r["mode"], "offline"); self.assertFalse(r["verdict"]["criteria_met"])
        self.assertIsNotNone(app.open_transport(r["payload"]))
    def test_follow_up_reuses_payload(self):
        r1 = app.handle_chat({"messages": TREM2})
        msgs = TREM2 + [{"role": "assistant", "content": r1["reply"]}, {"role": "user", "content": "Is it safe?"}]
        r2 = app.handle_chat({"messages": msgs, "payload": r1["payload"]})
        self.assertEqual(r2["payload"]["seal"], r1["payload"]["seal"])
        self.assertIn("can't interpret follow-up questions", r2["reply"])
    def test_tampered_payload_refused(self):
        r1 = app.handle_chat({"messages": TREM2})
        bad = dict(r1["payload"]); bad["canonical"] = bad["canonical"].replace('"met":false', '"met":true', 1)
        r = app.handle_chat({"messages": [{"role": "user", "content": "and?"}], "payload": bad})
        self.assertTrue(r.get("error")); self.assertIn("failed seal verification", r["reply"])
    def test_uploaded_target(self):
        t = json.load(open(os.path.join(os.path.dirname(__file__), "sample_target.json")))
        r = app.handle_chat({"messages": [{"role": "user", "content": "Run this"}], "target": t})
        self.assertIn("KRAS_G12C", r["reply"])
    def test_invalid_upload_rejected(self):
        r = app.handle_chat({"messages": [{"role": "user", "content": "Run"}], "target": {"target_name": "X"}})
        self.assertTrue(r.get("error"))
    def test_no_target_asks(self):
        r = app.handle_chat({"messages": [{"role": "user", "content": "hello"}]})
        self.assertIsNone(r["payload"])

if __name__ == "__main__":
    unittest.main(verbosity=2)
