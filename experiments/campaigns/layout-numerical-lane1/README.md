# Campaign layout-numerical-lane1

Export schema: `feyer-campaign-export-v1`. Snapshot: `2b010089a39d9f8ff0f959d78f0adae420fca6ab582a44ec8ff2f56135b6c3d8`.

[Frozen proposer context](contexts/f40d34a0338cd650066d09e1a80413ab8e48f7c9cb1fa56e2e806d5b6aba8288.json) — SHA256 `f40d34a0338cd650066d09e1a80413ab8e48f7c9cb1fa56e2e806d5b6aba8288`.

This is an evidence ledger. Scientific parents describe chosen inputs to an experiment; they are not necessarily Git parents. Phase changes are observations, not proof that one edit caused the difference. A failed attempt remains part of the history.

## Ownership and frozen policy

Campaign specification digest: `c5df55b766c3509dbd4b44bf174ee8bb8776d1f0731be0243569ac1af9828882`.

| Actor | Role | Ownership version | Active |
| --- | --- | --- | --- |
| coordinator | coordinator | 1 | True |

## Scientific lineage

Edges come from declared scientific parents, not inferred chronology or Git ancestry.

```mermaid
graph LR
  n0["topology-seed seed valid"]
  n1["3b5b664306504c809e532536e5e8b57a mutate proposed"]
  n0 -->|mutate| n1
```

## Candidate outcomes

| Candidate | Round / lane | Scientific parents | Exact commit | State | First-run seconds | Evidence IDs |
| --- | --- | --- | --- | --- | --- | --- |
| topology-seed | topology-001 / tune | root | e0a1dc69f4951c100fefbc9fc08a23c3c12058dc | valid | 22.7901 | be32d82593f043489d653a13f6e2694a:c6345924647cc627855ee6d3ee1a14b13eaf26fde6952a2277cef3f5046101b9 |
| 3b5b664306504c809e532536e5e8b57a | topology-001 / tune | topology-seed | 8c67d6f1d071aebb2e0d403288d5f08f17ae5469 | proposed | unknown | none |

## Round decisions and stalled work

### Round topology-001

Frozen specification: `3f0f3ed646e039f42d42286ac395d07432baf74ff9eac3701851199879a37f8b`; version: 1; closed: False.

```json
{
  "budget": {
    "deadline_unix": 1795296029.2574458,
    "max_evaluations": 16,
    "max_model_calls": 0,
    "max_proposals": 10
  },
  "dimensions": {
    "factor_mode": [
      "off",
      "direct"
    ],
    "merge_rhs": [
      true,
      false
    ],
    "noise_mode": [
      "broadcast",
      "shared"
    ],
    "split_rhs": [
      true,
      false
    ]
  },
  "lanes": {
    "tune": {
      "dimensions": [
        "noise_mode",
        "factor_mode",
        "split_rhs",
        "merge_rhs"
      ],
      "max_proposals": 9,
      "owner": "coordinator",
      "stall_limit": 9
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
        "noise_mode",
        "factor_mode",
        "split_rhs",
        "merge_rhs"
      ]
    }
  },
  "round_id": "topology-001",
  "seed_parameters": {
    "factor_mode": "off",
    "merge_rhs": true,
    "noise_mode": "broadcast",
    "split_rhs": true
  }
}
```

- topology-001/tune: active; owner coordinator; strikes 0; reason not recorded

## Candidate evidence and proposed changes

### topology-seed

```json
{
  "cohort_digest": "d78b193bdd3e61a0c054f0ba4b2645e67f80f7007e9e5fd6acea817f876795f6",
  "commit_sha": "e0a1dc69f4951c100fefbc9fc08a23c3c12058dc",
  "content_sha256": "fddf0e980eeabeda7f59782b59f9cb44487a2545dc84918de8359d3fddca1918",
  "context_sha256": null,
  "evaluation_requests": [
    {
      "attempt": 1,
      "candidate_id": "topology-seed",
      "evidence_id": "be32d82593f043489d653a13f6e2694a:c6345924647cc627855ee6d3ee1a14b13eaf26fde6952a2277cef3f5046101b9",
      "imported": true,
      "job_id": "be32d82593f043489d653a13f6e2694a",
      "profile": "full",
      "request_id": "2e3a5e0e99a1407c8ad7908867cf81b7",
      "status": "valid"
    }
  ],
  "evidence": [
    {
      "artifact_digest": "c6345924647cc627855ee6d3ee1a14b13eaf26fde6952a2277cef3f5046101b9",
      "artifact_digests": {
        "comparison.json": "15f8d46a404e1eefd7ec83ea4f7f55b145587a2b47fec4fa2c375c044307b5c3",
        "report.json": "3eacccfc4d9949dca21cc8d585c61fff0d1d1a9f744880a2510c5e4134379451",
        "result": "71afadfb7b3e0e7b6300d01d6430cd725cd3bfbceac92dbcaba50a0a8b3c11b4"
      },
      "candidate_sha": "e0a1dc69f4951c100fefbc9fc08a23c3c12058dc",
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
        "comparison_wall_seconds": 0.2793692760169506,
        "peak_rss_bytes": 8352460800,
        "peak_rss_kib": 8156700,
        "total_worker_wall_seconds": 89.53282411023974,
        "wall_seconds": 89.2534548342228
      },
      "eligible_full": true,
      "evidence_digest": "06ec3148d86fcea6c7079a871164c4da45a7c61b763715fd8bb58d680f5f13cd",
      "evidence_id": "be32d82593f043489d653a13f6e2694a:c6345924647cc627855ee6d3ee1a14b13eaf26fde6952a2277cef3f5046101b9",
      "execution_status": "completed",
      "issues": [],
      "job_id": "be32d82593f043489d653a13f6e2694a",
      "metrics": {
        "compilation": 11.172048164531589,
        "forward": 8.68656819500029,
        "gradient": 1.8111497070640326,
        "peak_rss_bytes": 8352460800,
        "runtime": 10.498919147998095,
        "sensitivity": 0.000886840745806694,
        "setup": 1.1191689353436232,
        "total": 22.790136247873306,
        "transfer": 0.0003144051879644394
      },
      "phases": {
        "build": 0.8141952250152826,
        "forward": 8.68656819500029,
        "forward_compile": 7.814133072271943,
        "forward_lower": 0.8559648208320141,
        "gradient": 1.8111497070640326,
        "gradient_compile": 1.9285775199532509,
        "gradient_lower": 0.19142693653702736,
        "host_transfer": 0.0003144051879644394,
        "imports": 0.30076025426387787,
        "initialize": 0.0027333125472068787,
        "load": 0.001480143517255783,
        "sensitivity": 0.000886840745806694,
        "sensitivity_compile": 0.2918199896812439,
        "sensitivity_lower": 0.09012582525610924
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
          "sampled_process_group_peak_rss_bytes": 8353509376,
          "samples": 323
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
          "differometor/build.py": "12a5690f48ca736fd9f0bd5301b3b3380a5f9f0b8754cc98781f39c9d413be9b",
          "differometor/components.py": "2e857e19d468d94b46594f71a76221d9d8b677bad05f6cf03b9e57b0e1613593",
          "differometor/plot.py": "16735e0fb14902f2c024e3da9f2655cbea634c4dd9e06c48af1247e12d0cf606",
          "differometor/setups.py": "478b1a7391b28604c36d8245e13ffa4f6d0f6dc32eeac6c6feaf5c08aa06a76b",
          "differometor/simulate.py": "5a33ffb5e6ee04474cd3637e15d55ca296e83e92f7216e011bccffc1e547ba94",
          "differometor/utils.py": "73ee8a862cbc435363904addc363071ed7dc8b1546956f82e1746998fe3b09ff"
        },
        "worker_sha256": "d3c212da0ab1215187407d9cd21dc2cbb5f88dc0b5ee7885135bf7f002d14b58"
      },
      "validated_output_scope": "last_warm_evaluation",
      "warm_metrics": {
        "forward": 9.067454723641276,
        "gradient": 1.8071485236287117,
        "host_transfer": 0.00026198476552963257,
        "sensitivity": 0.10972149111330509
      },
      "worker_error": null
    }
  ],
  "evidence_ids": [
    "be32d82593f043489d653a13f6e2694a:c6345924647cc627855ee6d3ee1a14b13eaf26fde6952a2277cef3f5046101b9"
  ],
  "git_parents": null,
  "heuristic_id": null,
  "hypothesis": null,
  "improved": false,
  "kind": "seed",
  "lane_id": "tune",
  "metrics": {
    "compilation": 11.172048164531589,
    "forward": 8.68656819500029,
    "gradient": 1.8111497070640326,
    "peak_rss_bytes": 8352460800,
    "runtime": 10.498919147998095,
    "sensitivity": 0.000886840745806694,
    "setup": 1.1191689353436232,
    "total": 22.790136247873306,
    "transfer": 0.0003144051879644394
  },
  "model_manifest": null,
  "owner": "coordinator",
  "owner_version": 1,
  "parameters": {
    "factor_mode": "off",
    "merge_rhs": true,
    "noise_mode": "broadcast",
    "split_rhs": true
  },
  "parameters_after": {
    "factor_mode": "off",
    "merge_rhs": true,
    "noise_mode": "broadcast",
    "split_rhs": true
  },
  "parameters_before": null,
  "parents": [],
  "prompt_sha256": null,
  "proposal": {
    "candidate_id": "topology-seed",
    "commit_sha": "e0a1dc69f4951c100fefbc9fc08a23c3c12058dc",
    "content_sha256": "fddf0e980eeabeda7f59782b59f9cb44487a2545dc84918de8359d3fddca1918",
    "kind": "seed",
    "lane_id": "tune",
    "parameters": {
      "factor_mode": "off",
      "merge_rhs": true,
      "noise_mode": "broadcast",
      "split_rhs": true
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

### 3b5b664306504c809e532536e5e8b57a

```json
{
  "cohort_digest": null,
  "commit_sha": "8c67d6f1d071aebb2e0d403288d5f08f17ae5469",
  "content_sha256": "01f68c636170e5a75ac3cc4880b56af6a2b7cc279405c5c4e56a7a019d9291dc",
  "context_sha256": null,
  "evaluation_requests": [],
  "evidence": [],
  "evidence_ids": [],
  "git_parents": null,
  "heuristic_id": null,
  "hypothesis": null,
  "improved": false,
  "kind": "mutate",
  "lane_id": "tune",
  "metrics": null,
  "model_manifest": null,
  "owner": "coordinator",
  "owner_version": 1,
  "parameters": {
    "factor_mode": "off",
    "merge_rhs": false,
    "noise_mode": "broadcast",
    "split_rhs": true
  },
  "parameters_after": {
    "factor_mode": "off",
    "merge_rhs": false,
    "noise_mode": "broadcast",
    "split_rhs": true
  },
  "parameters_before": null,
  "parents": [
    "topology-seed"
  ],
  "prompt_sha256": null,
  "proposal": {
    "candidate_id": "3b5b664306504c809e532536e5e8b57a",
    "commit_sha": "8c67d6f1d071aebb2e0d403288d5f08f17ae5469",
    "content_sha256": "01f68c636170e5a75ac3cc4880b56af6a2b7cc279405c5c4e56a7a019d9291dc",
    "kind": "mutate",
    "lane_id": "tune",
    "parameters": {
      "factor_mode": "off",
      "merge_rhs": false,
      "noise_mode": "broadcast",
      "split_rhs": true
    },
    "parents": [
      "topology-seed"
    ],
    "proposal_id": "3b5b664306504c809e532536e5e8b57a",
    "provenance": {
      "context": {
        "bytes": 1886,
        "path": "contexts/aef6e9e8dfdcf2c69d481cc61336979b9d0f225d52855c3e780338ed18ecb854.json",
        "sha256": "aef6e9e8dfdcf2c69d481cc61336979b9d0f225d52855c3e780338ed18ecb854"
      },
      "context_sha256": "6891a6542a965e349774d295927de82f2aada51e80d9ad4e5dcaf470f955464e",
      "heuristic_id": "exact-topology-smac-v1",
      "hypothesis": "Measure registered topology parameters under unchanged full correctness checks",
      "model": "SMAC3 random forest + expected improvement",
      "model_calls": 0,
      "model_trained": false,
      "origin": "local-startup",
      "selection_origin": "local-startup",
      "training_configurations": 1
    },
    "recipe": "tune",
    "round_id": "topology-001"
  },
  "proposal_id": "3b5b664306504c809e532536e5e8b57a",
  "provenance": {
    "context": {
      "bytes": 1886,
      "path": "contexts/aef6e9e8dfdcf2c69d481cc61336979b9d0f225d52855c3e780338ed18ecb854.json",
      "sha256": "aef6e9e8dfdcf2c69d481cc61336979b9d0f225d52855c3e780338ed18ecb854"
    },
    "context_sha256": "6891a6542a965e349774d295927de82f2aada51e80d9ad4e5dcaf470f955464e",
    "heuristic_id": "exact-topology-smac-v1",
    "hypothesis": "Measure registered topology parameters under unchanged full correctness checks",
    "model": "SMAC3 random forest + expected improvement",
    "model_calls": 0,
    "model_trained": false,
    "origin": "local-startup",
    "selection_origin": "local-startup",
    "training_configurations": 1
  },
  "recipe": "tune",
  "response_sha256": null,
  "round_id": "topology-001",
  "target_symbols": null,
  "uncertainty": "No repeat-confirmation or causality is inferred from this export. Inspect exact job evidence and matching cohorts.",
  "valid": false
}
```

## Decision and failure trail

| Sequence | Event | Actor | Detail |
| --- | --- | --- | --- |
| 1 | campaign_initialized | coordinator | {"spec_digest": "c5df55b766c3509dbd4b44bf174ee8bb8776d1f0731be0243569ac1af9828882"} |
| 2 | owner_claimed | coordinator | {"actor": "coordinator", "role": "coordinator", "version": 1} |
| 3 | round_created | coordinator | {"round_id": "topology-001", "spec_digest": "3f0f3ed646e039f42d42286ac395d07432baf74ff9eac3701851199879a37f8b", "version": 1} |
| 4 | candidate_proposed | coordinator | {"candidate_id": "topology-seed", "duplicate_of": null, "owner_version": 1, "proposal_digest": "c10c852a613fa75daf6c0a567d54f484a96669662ff462b364fda0246db8abe7", "proposal_id": "topology-seed"} |
| 5 | evidence_observed | coordinator | {"candidate_id": "topology-seed", "category": "valid", "evidence_digest": "764d7519b0a043491380335c9d5241917c2cd7f6e1bb77b25ab9893dfc62d2f6", "evidence_id": "be32d82593f043489d653a13f6e2694a:c6345924647cc627855ee6d3ee1a14b13eaf26fde6952a2277cef3f5046101b9", "job_id": "be32d82593f043489d653a13f6e2694a", "progress": null, "status": "valid", "strikes": 0} |
| 6 | decision_recorded | coordinator | {"decision_id": "3b5b664306504c809e532536e5e8b57a", "payload": {"context": {"bytes": 1886, "path": "contexts/aef6e9e8dfdcf2c69d481cc61336979b9d0f225d52855c3e780338ed18ecb854.json", "sha256": "aef6e9e8dfdcf2c69d481cc61336979b9d0f225d52855c3e780338ed18ecb854"}, "model_trained": false, "origin": "local-startup", "selection_origin": "local-startup", "training_configurations": 1}, "payload_digest": "f21480444689ad43f94d601fbd77bbaafe8143fb56013cf033e87c6aadccceb3"} |
| 7 | candidate_proposed | coordinator | {"candidate_id": "3b5b664306504c809e532536e5e8b57a", "duplicate_of": null, "owner_version": 1, "proposal_digest": "f3862682eb6be8e805aa6b1300fef1e6e6abe7259aa8bab8ad7fd446394c2fc0", "proposal_id": "3b5b664306504c809e532536e5e8b57a"} |

Guidance may propose a new round. It cannot silently replace frozen operators, ownership, evaluation requirements or budgets. Only the coordinator can admit that round through the campaign state API. Publishing this ledger does not merge or promote candidate code.
