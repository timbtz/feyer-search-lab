# Campaign astra-group-numerical-v3

Export schema: `feyer-campaign-export-v1`. Snapshot: `44f699a6c3a065121ee9d062c9cb03d781283ad6918230c345833bce3f2c4f25`.

[Frozen proposer context](contexts/bb880313b8ac253c48ea000254c145f13f5dc7a174f817f2405f592a7a3aa5f2.json) — SHA256 `bb880313b8ac253c48ea000254c145f13f5dc7a174f817f2405f592a7a3aa5f2`.

This is an evidence ledger. Scientific parents describe chosen inputs to an experiment; they are not necessarily Git parents. Phase changes are observations, not proof that one edit caused the difference. A failed attempt remains part of the history.

## Ownership and frozen policy

Campaign specification digest: `8b8410471ed01c330053fe804096c8192d1f88f6f479870966200d4be25156bd`.

| Actor | Role | Ownership version | Active |
| --- | --- | --- | --- |
| coordinator | coordinator | 1 | True |

## Scientific lineage

Edges come from declared scientific parents, not inferred chronology or Git ancestry.

```mermaid
graph LR
  n0["topology-seed seed valid"]
```

## Candidate outcomes

| Candidate | Round / lane | Scientific parents | Exact commit | State | First-run seconds | Evidence IDs |
| --- | --- | --- | --- | --- | --- | --- |
| topology-seed | topology-001 / tune | root | d947905c9b73e310257235cf00cb065c31572ecd | valid | 21.5603 | 15ca7b7e27964b7c94b545d4b95849b8:deef0589aa1f4f4cd34404821f265dbb6b22a4cc8efb2b28e471412e2828c87d |

## Round decisions and stalled work

### Round topology-001

Frozen specification: `91641037b53366cbe8399a98c9e9109c18a3bc364ffea17edc3a90b025ff54ce`; version: 1; closed: False.

```json
{
  "budget": {
    "deadline_unix": 1795299882.878179,
    "max_evaluations": 10,
    "max_model_calls": 0,
    "max_proposals": 7
  },
  "dimensions": {
    "group_checkpoint": [
      "existing",
      "cse_barrier",
      "disabled"
    ],
    "group_inline": [
      true,
      false
    ]
  },
  "lanes": {
    "tune": {
      "dimensions": [
        "group_inline",
        "group_checkpoint"
      ],
      "max_proposals": 6,
      "owner": "coordinator",
      "stall_limit": 6
    }
  },
  "materializer_version": "exact-topology-finite-v1",
  "progress": {
    "absolute": 0.02,
    "relative": 0.01
  },
  "recipes": {
    "tune": {
      "dimensions": [
        "group_inline",
        "group_checkpoint"
      ]
    }
  },
  "round_id": "topology-001",
  "seed_parameters": {
    "group_checkpoint": "existing",
    "group_inline": true
  }
}
```

- topology-001/tune: ready; owner coordinator; strikes 0; reason not recorded

## Candidate evidence and proposed changes

### topology-seed

```json
{
  "cohort_digest": "d78b193bdd3e61a0c054f0ba4b2645e67f80f7007e9e5fd6acea817f876795f6",
  "commit_sha": "d947905c9b73e310257235cf00cb065c31572ecd",
  "content_sha256": "fe4f9f610d353d13baebe4189a1e5fa83a5b98450168b3ccf7958ce4b484c95e",
  "context_sha256": null,
  "evaluation_requests": [
    {
      "attempt": 1,
      "candidate_id": "topology-seed",
      "evidence_id": "15ca7b7e27964b7c94b545d4b95849b8:deef0589aa1f4f4cd34404821f265dbb6b22a4cc8efb2b28e471412e2828c87d",
      "imported": true,
      "job_id": "15ca7b7e27964b7c94b545d4b95849b8",
      "profile": "full",
      "request_id": "04eefb40a74d4b709e0a87e29e4fa06a",
      "status": "valid"
    }
  ],
  "evidence": [
    {
      "artifact_digest": "deef0589aa1f4f4cd34404821f265dbb6b22a4cc8efb2b28e471412e2828c87d",
      "artifact_digests": {
        "comparison.json": "a757270aa2d5140cc4d0cdfdea136f573407c914e2f72027d11df12b7dae87d6",
        "report.json": "3c144030e30133af3e7de6906854e908b7863911abcdd9cba1b1636348c1f8d1",
        "result": "de937061ee2777d1bb2b1d631184042af1de7953c9b8d103072d8ea6fd12546a"
      },
      "candidate_sha": "d947905c9b73e310257235cf00cb065c31572ecd",
      "category": "valid",
      "checks": {
        "official": "passed",
        "precision": "passed",
        "resource": "passed",
        "source": "passed",
        "strict": "passed",
        "workload": "passed"
      },
      "cohort": {
        "adapter_schema": "feyer-evolution-evidence-v1",
        "container_limits": {
          "cpu.max": "1600000 100000",
          "cpuset.cpus.effective": "0-127",
          "memory.max": "59055800320",
          "memory.swap.max": "0"
        },
        "memory_policy": {
          "budget_bytes": 16000000000,
          "enforcement": "sampled_process_group_rss",
          "kernel_memory_limit_enforced": false
        },
        "profile": "full",
        "protected_baseline_sha": "02ec741d8a1bf1a2278294ea74f9fc1d68f08f1f",
        "signature": {
          "environment": {
            "backend": "cpu",
            "cpu_affinity_ids": [
              34
            ],
            "cpu_model": "AMD EPYC 9334 32-Core Processor",
            "jax_enable_x64": true,
            "packages": {
              "differometor": "0.0.6",
              "jax": "0.9.0",
              "jaxlib": "0.9.0",
              "numpy": "2.5.5",
              "optax": "0.2.6"
            },
            "persistent_compilation_cache": false,
            "python": "3.12.15",
            "requested_logical_cpus": 1,
            "thread_limits": {
              "MKL_NUM_THREADS": "1",
              "NUMEXPR_NUM_THREADS": "1",
              "OMP_NUM_THREADS": "1",
              "OPENBLAS_NUM_THREADS": "1"
            },
            "xla_flags": null
          },
          "inputs": {
            "frequency_count": 101,
            "gradient_parameter_count": 193,
            "reference_sha256": "726f2cfe6986cb991fa48d5a28127b9330c3dc7e69d5bd193c8748acef03adc3",
            "setup_sha256": "ff4ba353a2a03cdce7f3e61bad729c2e00888d842c28ba9cf699f95afb87e138"
          },
          "timing": {
            "benchmark": "start-munich-2026-public-differometor-uifo-v2",
            "evaluator_sha256": "d5950bbd872e5b00ad63f0bd7081e5096fb14ba9c96c80a6854a3b714719bd4e",
            "phase_keys": [
              "build",
              "forward",
              "forward_compile",
              "forward_lower",
              "gradient",
              "gradient_compile",
              "gradient_lower",
              "host_transfer",
              "imports",
              "initialize",
              "load",
              "sensitivity",
              "sensitivity_compile",
              "sensitivity_lower"
            ],
            "scope": {
              "excluded": "validation and benchmark harness bookkeeping, repeated profiling, plot/report generation; interpreter launch before the first timer",
              "forward_residuals": "saved for separately compiled reverse pass",
              "gradient_coordinates": "physical parameter values; public grid-length tying",
              "objective": "mean(log10(sensitivity / public_reference))",
              "optimizer_steps": 0,
              "total_scope": "imports, CPU initialization, input I/O, setup, all lowering/compilation, forward, sensitivity/powers/loss, reverse-mode gradient and host transfer"
            }
          }
        },
        "strict_policy": {
          "evaluator_sha256": "1bc9b39fe0023afc3db93211b9e3d6cd37ed2b13ee281f142749c2237a16ea8f",
          "reference_arrays_sha256": "c3f6cba045f8b41f488dc19c960f5056b5f2e75cfa64f9a687b52f2a9ba2751e",
          "rtol": 1e-07,
          "scale_atol": 1e-12
        },
        "worker_sha256": "d3c212da0ab1215187407d9cd21dc2cbb5f88dc0b5ee7885135bf7f002d14b58"
      },
      "cohort_digest": "d78b193bdd3e61a0c054f0ba4b2645e67f80f7007e9e5fd6acea817f876795f6",
      "cost": {
        "comparison_wall_seconds": 0.284583380445838,
        "peak_rss_bytes": 8030789632,
        "peak_rss_kib": 7842568,
        "total_worker_wall_seconds": 90.31826015748084,
        "wall_seconds": 90.033676777035
      },
      "eligible_full": true,
      "evidence_digest": "8dd39cfed5e1f9cf6551203e4d75e848a1304d9c5eeb6b90dd9aa002508f5814",
      "evidence_id": "15ca7b7e27964b7c94b545d4b95849b8:deef0589aa1f4f4cd34404821f265dbb6b22a4cc8efb2b28e471412e2828c87d",
      "execution_status": "completed",
      "issues": [],
      "job_id": "15ca7b7e27964b7c94b545d4b95849b8",
      "metrics": {
        "compilation": 9.826732682064176,
        "forward": 9.00551001727581,
        "gradient": 1.5804204046726227,
        "peak_rss_bytes": 8030789632,
        "runtime": 10.587104961276054,
        "sensitivity": 0.0008732229471206665,
        "setup": 1.1464195474982262,
        "total": 21.560257190838456,
        "transfer": 0.00030131638050079346
      },
      "phases": {
        "build": 0.8380487989634275,
        "forward": 9.00551001727581,
        "forward_compile": 3.554601876065135,
        "forward_lower": 0.765934482216835,
        "gradient": 1.5804204046726227,
        "gradient_compile": 4.759547900408506,
        "gradient_lower": 0.32987051270902157,
        "host_transfer": 0.00030131638050079346,
        "imports": 0.3042175006121397,
        "initialize": 0.0027419906109571457,
        "load": 0.0014112573117017746,
        "sensitivity": 0.0008732229471206665,
        "sensitivity_compile": 0.33775004744529724,
        "sensitivity_lower": 0.07902786321938038
      },
      "profile": "full",
      "resource_evidence": {
        "budget_bytes": 16000000000,
        "container_limits": {
          "cpu.max": "1600000 100000",
          "cpuset.cpus.effective": "0-127",
          "memory.max": "59055800320",
          "memory.swap.max": "0"
        },
        "limitation": "Sampled process-group RSS is not a kernel-enforced memory cap.",
        "memory_monitoring": {
          "budget_bytes": 16000000000,
          "enforcement": "sampled_process_group_rss",
          "exceeded": false,
          "kernel_memory_limit_enforced": false,
          "notes": "RSS sampling can miss brief peaks and counts shared pages in each process. It excludes GPU VRAM and does not reserve RAM or constrain other instance work.",
          "sampled_process_group_peak_rss_bytes": 8031838208,
          "samples": 322
        }
      },
      "schema_version": "feyer-evolution-evidence-v1",
      "scientific_strike": false,
      "screen_passed": false,
      "source_digests": {
        "clean_diff_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "comparison_evaluator_sha256": "1bc9b39fe0023afc3db93211b9e3d6cd37ed2b13ee281f142749c2237a16ea8f",
        "evaluator_sha256": "d5950bbd872e5b00ad63f0bd7081e5096fb14ba9c96c80a6854a3b714719bd4e",
        "reference_arrays_sha256": "c3f6cba045f8b41f488dc19c960f5056b5f2e75cfa64f9a687b52f2a9ba2751e",
        "simulator_files_sha256": {
          "differometor/__init__.py": "505d559d5a17409680a91f555882edf23f78cbb7c98ee28845018fa9bfeba7e7",
          "differometor/build.py": "40f79573097e6037f70a5c89e1098f96cbffb9c8a87fc94d2ed34ab6756ab63d",
          "differometor/components.py": "2e857e19d468d94b46594f71a76221d9d8b677bad05f6cf03b9e57b0e1613593",
          "differometor/plot.py": "16735e0fb14902f2c024e3da9f2655cbea634c4dd9e06c48af1247e12d0cf606",
          "differometor/setups.py": "478b1a7391b28604c36d8245e13ffa4f6d0f6dc32eeac6c6feaf5c08aa06a76b",
          "differometor/simulate.py": "37ac18d969cebcda6fb1b26ae394be1ad39b062c3a2703b3450c90fe81ecc5df",
          "differometor/utils.py": "73ee8a862cbc435363904addc363071ed7dc8b1546956f82e1746998fe3b09ff"
        },
        "worker_sha256": "d3c212da0ab1215187407d9cd21dc2cbb5f88dc0b5ee7885135bf7f002d14b58"
      },
      "validated_output_scope": "last_warm_evaluation",
      "warm_metrics": {
        "forward": 9.370900511741638,
        "gradient": 1.5783772002905607,
        "host_transfer": 0.00020226649940013885,
        "sensitivity": 0.18347955495119095
      },
      "worker_error": null
    }
  ],
  "evidence_ids": [
    "15ca7b7e27964b7c94b545d4b95849b8:deef0589aa1f4f4cd34404821f265dbb6b22a4cc8efb2b28e471412e2828c87d"
  ],
  "git_parents": null,
  "heuristic_id": null,
  "hypothesis": null,
  "improved": false,
  "kind": "seed",
  "lane_id": "tune",
  "metrics": {
    "compilation": 9.826732682064176,
    "forward": 9.00551001727581,
    "gradient": 1.5804204046726227,
    "peak_rss_bytes": 8030789632,
    "runtime": 10.587104961276054,
    "sensitivity": 0.0008732229471206665,
    "setup": 1.1464195474982262,
    "total": 21.560257190838456,
    "transfer": 0.00030131638050079346
  },
  "model_manifest": null,
  "owner": "coordinator",
  "owner_version": 1,
  "parameters": {
    "group_checkpoint": "existing",
    "group_inline": true
  },
  "parameters_after": {
    "group_checkpoint": "existing",
    "group_inline": true
  },
  "parameters_before": null,
  "parents": [],
  "prompt_sha256": null,
  "proposal": {
    "candidate_id": "topology-seed",
    "commit_sha": "d947905c9b73e310257235cf00cb065c31572ecd",
    "content_sha256": "fe4f9f610d353d13baebe4189a1e5fa83a5b98450168b3ccf7958ce4b484c95e",
    "kind": "seed",
    "lane_id": "tune",
    "parameters": {
      "group_checkpoint": "existing",
      "group_inline": true
    },
    "parents": [],
    "proposal_id": "topology-seed",
    "provenance": {
      "heuristic_id": "import-exact-claude-topology",
      "model_calls": 0
    },
    "recipe": null,
    "round_id": "topology-001"
  },
  "proposal_id": "topology-seed",
  "provenance": {
    "heuristic_id": "import-exact-claude-topology",
    "model_calls": 0
  },
  "recipe": null,
  "response_sha256": null,
  "round_id": "topology-001",
  "target_symbols": null,
  "uncertainty": "No repeat-confirmation or causality is inferred from this export. Inspect exact job evidence and matching cohorts.",
  "valid": true
}
```

## Decision and failure trail

| Sequence | Event | Actor | Detail |
| --- | --- | --- | --- |
| 1 | campaign_initialized | coordinator | {"spec_digest": "8b8410471ed01c330053fe804096c8192d1f88f6f479870966200d4be25156bd"} |
| 2 | owner_claimed | coordinator | {"actor": "coordinator", "role": "coordinator", "version": 1} |
| 3 | round_created | coordinator | {"round_id": "topology-001", "spec_digest": "91641037b53366cbe8399a98c9e9109c18a3bc364ffea17edc3a90b025ff54ce", "version": 1} |
| 4 | candidate_proposed | coordinator | {"candidate_id": "topology-seed", "duplicate_of": null, "owner_version": 1, "proposal_digest": "29e3eb5e409f235958e19836ad37b21dd211c02f791a6082bb511e5c9f6f2684", "proposal_id": "topology-seed"} |
| 5 | evidence_observed | coordinator | {"candidate_id": "topology-seed", "category": "valid", "evidence_digest": "e2b1200f475ec0e799d7bfaa78bd025fc61f1b0487413eec804fcad70b4befe1", "evidence_id": "15ca7b7e27964b7c94b545d4b95849b8:deef0589aa1f4f4cd34404821f265dbb6b22a4cc8efb2b28e471412e2828c87d", "job_id": "15ca7b7e27964b7c94b545d4b95849b8", "progress": null, "status": "valid", "strikes": 0} |
| 6 | decision_recorded | coordinator | {"decision_id": "a8efe304420645edaf27424096a5f054", "payload": {"context": {"bytes": 1386, "path": "contexts/8030afbf0f1c2566c033645307a93b62afb24271301dc60920460ba01d9ec31f.json", "sha256": "8030afbf0f1c2566c033645307a93b62afb24271301dc60920460ba01d9ec31f"}, "model_trained": false, "origin": "local-startup", "selection_origin": "local-startup", "training_configurations": 1}, "payload_digest": "0aef9292dee4cdaf33da16e3fc7b32ac6a83d657e088186a2e6e7dc3d4f8c989"} |

Guidance may propose a new round. It cannot silently replace frozen operators, ownership, evaluation requirements or budgets. Only the coordinator can admit that round through the campaign state API. Publishing this ledger does not merge or promote candidate code.
