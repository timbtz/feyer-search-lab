# Campaign layout-numerical-lane1

Export schema: `feyer-campaign-export-v1`. Snapshot: `9c64da2a366fc9301798fe7924855546cfd79c9a1be0334755b7b53a9608c637`.

[Frozen proposer context](contexts/304bc71c642ff0458124a6a9fd269e07c736a90ce652887e3bafe26a84c70095.json) — SHA256 `304bc71c642ff0458124a6a9fd269e07c736a90ce652887e3bafe26a84c70095`.

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
  n1["3b5b664306504c809e532536e5e8b57a mutate valid"]
  n2["530091c8ae754deb85cc3bdb35699d31 mutate valid"]
  n3["936f1b7d45c14ffc823c45610b592529 mutate valid"]
  n0 -->|mutate| n1
  n0 -->|mutate| n2
  n0 -->|mutate| n3
```

## Candidate outcomes

| Candidate | Round / lane | Scientific parents | Exact commit | State | First-run seconds | Evidence IDs |
| --- | --- | --- | --- | --- | --- | --- |
| topology-seed | topology-001 / tune | root | e0a1dc69f4951c100fefbc9fc08a23c3c12058dc | valid | 22.7901 | be32d82593f043489d653a13f6e2694a:c6345924647cc627855ee6d3ee1a14b13eaf26fde6952a2277cef3f5046101b9 |
| 3b5b664306504c809e532536e5e8b57a | topology-001 / tune | topology-seed | 8c67d6f1d071aebb2e0d403288d5f08f17ae5469 | valid | 23.2203 | 335506602662421987d0b851acf3d593:74d94f798c1cfa797259c64b1bba4b07b4b37554c2b1aa823af6af675a89bc12, 67de6c4aaf024c959b71352e7e54339b:c5a039f8f44ebd6fde56c5d65f9ffbcdb9510342d377312270fbce2fd819eec5 |
| 530091c8ae754deb85cc3bdb35699d31 | topology-001 / tune | topology-seed | ea8d294e7198db5cfb549502fa7872d44789da2b | valid | 23.2223 | bbfbe5f3d20a454d8516163ffea58c7b:3005be8311ae979640c085c30391ead859297cd43a05f84d6082458378556832, 0ce31ea937834cf48fd2c0b4967aeb58:c4ba2de11c76b49f4b648d3125a34fa342ef96bd269cca1fcdef71e50147af60 |
| 936f1b7d45c14ffc823c45610b592529 | topology-001 / tune | topology-seed | 4e575979c72e42a7a78f2f1aabda9477f6c4c109 | valid | 22.9817 | 1b8d66f317c740fa876eccfe0fd2372e:f8c72d105e44c9a2a9ac4d06f6d1c2cef89dc946ed25255c3b0eccec36644512, 2c21770160cc46239770fce8d5638933:355a713605c5752599403be59ec18612d75aa87339800c90dac495d69f4fb8ed |

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

- topology-001/tune: ready; owner coordinator; strikes 3; reason not recorded

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
  "cohort_digest": "d78b193bdd3e61a0c054f0ba4b2645e67f80f7007e9e5fd6acea817f876795f6",
  "commit_sha": "8c67d6f1d071aebb2e0d403288d5f08f17ae5469",
  "content_sha256": "01f68c636170e5a75ac3cc4880b56af6a2b7cc279405c5c4e56a7a019d9291dc",
  "context_sha256": null,
  "evaluation_requests": [
    {
      "attempt": 1,
      "candidate_id": "3b5b664306504c809e532536e5e8b57a",
      "evidence_id": "335506602662421987d0b851acf3d593:74d94f798c1cfa797259c64b1bba4b07b4b37554c2b1aa823af6af675a89bc12",
      "imported": false,
      "job_id": "335506602662421987d0b851acf3d593",
      "profile": "screen",
      "request_id": "6a9ea2bb79154fbfbb0d2946c6320ae1",
      "status": "screen"
    },
    {
      "attempt": 1,
      "candidate_id": "3b5b664306504c809e532536e5e8b57a",
      "evidence_id": "67de6c4aaf024c959b71352e7e54339b:c5a039f8f44ebd6fde56c5d65f9ffbcdb9510342d377312270fbce2fd819eec5",
      "imported": false,
      "job_id": "67de6c4aaf024c959b71352e7e54339b",
      "profile": "full",
      "request_id": "faebcace3e244e358d75006fe690e318",
      "status": "valid"
    }
  ],
  "evidence": [
    {
      "artifact_digest": "74d94f798c1cfa797259c64b1bba4b07b4b37554c2b1aa823af6af675a89bc12",
      "artifact_digests": {
        "report.json": "315fd14239c7ac72e8ad08cc0e3a89af5a66b00e56f6493a10864461fea93c73",
        "result": "add6c88ec695f192d6c1f066cc5db95c202ca2f1a3ab3c3c70d5dc66529259c5"
      },
      "candidate_sha": "8c67d6f1d071aebb2e0d403288d5f08f17ae5469",
      "category": "screen",
      "checks": {
        "official": "not_run",
        "precision": "passed",
        "resource": "passed",
        "source": "passed",
        "strict": "not_run",
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
        "profile": "screen",
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
        "strict_policy": null,
        "worker_sha256": "d3c212da0ab1215187407d9cd21dc2cbb5f88dc0b5ee7885135bf7f002d14b58"
      },
      "cohort_digest": "465a1051caf482041d73c67eca828452830dcc12021b720faaa0f3ab3e41cebb",
      "cost": {
        "peak_rss_bytes": 9228451840,
        "peak_rss_kib": 9012160,
        "total_worker_wall_seconds": 24.410811502486467,
        "wall_seconds": 24.410811502486467
      },
      "eligible_full": false,
      "evidence_digest": "09cfa2bec8f1a7d0c3b819e88d15674dd976ab2804a34441c988519c10309093",
      "evidence_id": "335506602662421987d0b851acf3d593:74d94f798c1cfa797259c64b1bba4b07b4b37554c2b1aa823af6af675a89bc12",
      "execution_status": "completed",
      "issues": [],
      "job_id": "335506602662421987d0b851acf3d593",
      "metrics": {
        "compilation": 11.178435128182173,
        "forward": 9.05685455352068,
        "gradient": 1.8885404095053673,
        "peak_rss_bytes": 9228451840,
        "runtime": 10.946584228426218,
        "sensitivity": 0.0008539501577615738,
        "setup": 1.1333500370383263,
        "total": 23.258369393646717,
        "transfer": 0.0003353152424097061
      },
      "phases": {
        "build": 0.8234314043074846,
        "forward": 9.05685455352068,
        "forward_compile": 7.861363155767322,
        "forward_lower": 0.8509230688214302,
        "gradient": 1.8885404095053673,
        "gradient_compile": 1.9121511485427618,
        "gradient_lower": 0.18865378759801388,
        "host_transfer": 0.0003353152424097061,
        "imports": 0.30571616627275944,
        "initialize": 0.002776229754090309,
        "load": 0.00142623670399189,
        "sensitivity": 0.0008539501577615738,
        "sensitivity_compile": 0.2786077465862036,
        "sensitivity_lower": 0.08673622086644173
      },
      "profile": "screen",
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
          "sampled_process_group_peak_rss_bytes": 9229500416,
          "samples": 88
        }
      },
      "schema_version": "feyer-evolution-evidence-v1",
      "scientific_strike": false,
      "screen_passed": true,
      "source_digests": {
        "clean_diff_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "evaluator_sha256": "2bf4249e453271d1f665c35356485739ad66a9b0327153d678a5b34d81192458",
        "simulator_files_sha256": {
          "differometor/__init__.py": "505d559d5a17409680a91f555882edf23f78cbb7c98ee28845018fa9bfeba7e7",
          "differometor/build.py": "12a5690f48ca736fd9f0bd5301b3b3380a5f9f0b8754cc98781f39c9d413be9b",
          "differometor/components.py": "2e857e19d468d94b46594f71a76221d9d8b677bad05f6cf03b9e57b0e1613593",
          "differometor/plot.py": "16735e0fb14902f2c024e3da9f2655cbea634c4dd9e06c48af1247e12d0cf606",
          "differometor/setups.py": "478b1a7391b28604c36d8245e13ffa4f6d0f6dc32eeac6c6feaf5c08aa06a76b",
          "differometor/simulate.py": "f8adbb9fe6a6bccf850ce1a91be4c3b7b4d05692c2e774851d560cfcbfc41932",
          "differometor/utils.py": "73ee8a862cbc435363904addc363071ed7dc8b1546956f82e1746998fe3b09ff"
        },
        "worker_sha256": "d3c212da0ab1215187407d9cd21dc2cbb5f88dc0b5ee7885135bf7f002d14b58"
      },
      "validated_output_scope": "first_evaluation",
      "warm_metrics": {},
      "worker_error": null
    },
    {
      "artifact_digest": "c5a039f8f44ebd6fde56c5d65f9ffbcdb9510342d377312270fbce2fd819eec5",
      "artifact_digests": {
        "comparison.json": "53db6296074a20f8e3e7d78deadfb85143c844ea4844432e77356e1aabd3110c",
        "report.json": "a0cdeb9bb6737e547145aecd2e05278727cd305e563c77a8830e9405c7403f05",
        "result": "612df0cad64b7c563409d7b9aae83f24d8f793587729cae5564b97c16c6740c7"
      },
      "candidate_sha": "8c67d6f1d071aebb2e0d403288d5f08f17ae5469",
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
        "comparison_wall_seconds": 0.28058770298957825,
        "peak_rss_bytes": 9228156928,
        "peak_rss_kib": 9011872,
        "total_worker_wall_seconds": 92.12811331637204,
        "wall_seconds": 91.84752561338246
      },
      "eligible_full": true,
      "evidence_digest": "57e5dc0d22c23449130104ccf5759679a4374b3ca1afa757cb333ea17789a3f2",
      "evidence_id": "67de6c4aaf024c959b71352e7e54339b:c5a039f8f44ebd6fde56c5d65f9ffbcdb9510342d377312270fbce2fd819eec5",
      "execution_status": "completed",
      "issues": [],
      "job_id": "67de6c4aaf024c959b71352e7e54339b",
      "metrics": {
        "compilation": 11.168694706633687,
        "forward": 9.033618746325374,
        "gradient": 1.901908177882433,
        "peak_rss_bytes": 9228156928,
        "runtime": 10.936733102425933,
        "sensitivity": 0.0008833631873130798,
        "setup": 1.1148661114275455,
        "total": 23.220293920487165,
        "transfer": 0.00032281503081321716
      },
      "phases": {
        "build": 0.8121926169842482,
        "forward": 9.033618746325374,
        "forward_compile": 7.783842878416181,
        "forward_lower": 0.8365299291908741,
        "gradient": 1.901908177882433,
        "gradient_compile": 1.9200779106467962,
        "gradient_lower": 0.18832200206816196,
        "host_transfer": 0.00032281503081321716,
        "imports": 0.2984363418072462,
        "initialize": 0.0027464404702186584,
        "load": 0.0014907121658325195,
        "sensitivity": 0.0008833631873130798,
        "sensitivity_compile": 0.3496754728257656,
        "sensitivity_lower": 0.09024651348590851
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
          "sampled_process_group_peak_rss_bytes": 9229205504,
          "samples": 332
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
          "differometor/simulate.py": "f8adbb9fe6a6bccf850ce1a91be4c3b7b4d05692c2e774851d560cfcbfc41932",
          "differometor/utils.py": "73ee8a862cbc435363904addc363071ed7dc8b1546956f82e1746998fe3b09ff"
        },
        "worker_sha256": "d3c212da0ab1215187407d9cd21dc2cbb5f88dc0b5ee7885135bf7f002d14b58"
      },
      "validated_output_scope": "last_warm_evaluation",
      "warm_metrics": {
        "forward": 9.551100613549352,
        "gradient": 1.8859653528779745,
        "host_transfer": 0.00022199749946594238,
        "sensitivity": 0.11717049591243267
      },
      "worker_error": null
    }
  ],
  "evidence_ids": [
    "335506602662421987d0b851acf3d593:74d94f798c1cfa797259c64b1bba4b07b4b37554c2b1aa823af6af675a89bc12",
    "67de6c4aaf024c959b71352e7e54339b:c5a039f8f44ebd6fde56c5d65f9ffbcdb9510342d377312270fbce2fd819eec5"
  ],
  "git_parents": null,
  "heuristic_id": null,
  "hypothesis": null,
  "improved": false,
  "kind": "mutate",
  "lane_id": "tune",
  "metrics": {
    "compilation": 11.168694706633687,
    "forward": 9.033618746325374,
    "gradient": 1.901908177882433,
    "peak_rss_bytes": 9228156928,
    "runtime": 10.936733102425933,
    "sensitivity": 0.0008833631873130798,
    "setup": 1.1148661114275455,
    "total": 23.220293920487165,
    "transfer": 0.00032281503081321716
  },
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
  "valid": true
}
```

### 530091c8ae754deb85cc3bdb35699d31

```json
{
  "cohort_digest": "d78b193bdd3e61a0c054f0ba4b2645e67f80f7007e9e5fd6acea817f876795f6",
  "commit_sha": "ea8d294e7198db5cfb549502fa7872d44789da2b",
  "content_sha256": "d52e92a07a86511728d0cc8e48f448726e8deaa0e89e0079e1e2c157f046b1a7",
  "context_sha256": null,
  "evaluation_requests": [
    {
      "attempt": 1,
      "candidate_id": "530091c8ae754deb85cc3bdb35699d31",
      "evidence_id": "bbfbe5f3d20a454d8516163ffea58c7b:3005be8311ae979640c085c30391ead859297cd43a05f84d6082458378556832",
      "imported": false,
      "job_id": "bbfbe5f3d20a454d8516163ffea58c7b",
      "profile": "screen",
      "request_id": "8a30968d281141d69d107ffe7b793ff5",
      "status": "screen"
    },
    {
      "attempt": 1,
      "candidate_id": "530091c8ae754deb85cc3bdb35699d31",
      "evidence_id": "0ce31ea937834cf48fd2c0b4967aeb58:c4ba2de11c76b49f4b648d3125a34fa342ef96bd269cca1fcdef71e50147af60",
      "imported": false,
      "job_id": "0ce31ea937834cf48fd2c0b4967aeb58",
      "profile": "full",
      "request_id": "c748ce60974b4743a4711db3bfee3bb1",
      "status": "valid"
    }
  ],
  "evidence": [
    {
      "artifact_digest": "3005be8311ae979640c085c30391ead859297cd43a05f84d6082458378556832",
      "artifact_digests": {
        "report.json": "d3cd9ea68b404cc405311d0b070ff8a87b7497b2817941ddab8da9cb071f3236",
        "result": "77784ef9c8e2c55d601eead43722f2d1cdc02328ed050c50e49e893bac3217cf"
      },
      "candidate_sha": "ea8d294e7198db5cfb549502fa7872d44789da2b",
      "category": "screen",
      "checks": {
        "official": "not_run",
        "precision": "passed",
        "resource": "passed",
        "source": "passed",
        "strict": "not_run",
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
        "profile": "screen",
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
        "strict_policy": null,
        "worker_sha256": "d3c212da0ab1215187407d9cd21dc2cbb5f88dc0b5ee7885135bf7f002d14b58"
      },
      "cohort_digest": "465a1051caf482041d73c67eca828452830dcc12021b720faaa0f3ab3e41cebb",
      "cost": {
        "peak_rss_bytes": 8347328512,
        "peak_rss_kib": 8151688,
        "total_worker_wall_seconds": 24.42075377702713,
        "wall_seconds": 24.42075377702713
      },
      "eligible_full": false,
      "evidence_digest": "e07939f7a835540d4069d667353be3cee3ab1f0b32c930300bebde0d5546f319",
      "evidence_id": "bbfbe5f3d20a454d8516163ffea58c7b:3005be8311ae979640c085c30391ead859297cd43a05f84d6082458378556832",
      "execution_status": "completed",
      "issues": [],
      "job_id": "bbfbe5f3d20a454d8516163ffea58c7b",
      "metrics": {
        "compilation": 11.305473819375038,
        "forward": 8.868868237361312,
        "gradient": 1.9124682024121284,
        "peak_rss_bytes": 8347328512,
        "runtime": 10.782622694969177,
        "sensitivity": 0.0009296592324972153,
        "setup": 1.1250644624233246,
        "total": 23.21316097676754,
        "transfer": 0.0003565959632396698
      },
      "phases": {
        "build": 0.8204605299979448,
        "forward": 8.868868237361312,
        "forward_compile": 7.833754988387227,
        "forward_lower": 0.8603187724947929,
        "gradient": 1.9124682024121284,
        "gradient_compile": 1.9256355110555887,
        "gradient_lower": 0.21015353687107563,
        "host_transfer": 0.0003565959632396698,
        "imports": 0.30030106753110886,
        "initialize": 0.002781519666314125,
        "load": 0.0015213452279567719,
        "sensitivity": 0.0009296592324972153,
        "sensitivity_compile": 0.3664124794304371,
        "sensitivity_lower": 0.10919853113591671
      },
      "profile": "screen",
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
          "sampled_process_group_peak_rss_bytes": 8348377088,
          "samples": 88
        }
      },
      "schema_version": "feyer-evolution-evidence-v1",
      "scientific_strike": false,
      "screen_passed": true,
      "source_digests": {
        "clean_diff_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "evaluator_sha256": "2bf4249e453271d1f665c35356485739ad66a9b0327153d678a5b34d81192458",
        "simulator_files_sha256": {
          "differometor/__init__.py": "505d559d5a17409680a91f555882edf23f78cbb7c98ee28845018fa9bfeba7e7",
          "differometor/build.py": "12a5690f48ca736fd9f0bd5301b3b3380a5f9f0b8754cc98781f39c9d413be9b",
          "differometor/components.py": "2e857e19d468d94b46594f71a76221d9d8b677bad05f6cf03b9e57b0e1613593",
          "differometor/plot.py": "16735e0fb14902f2c024e3da9f2655cbea634c4dd9e06c48af1247e12d0cf606",
          "differometor/setups.py": "478b1a7391b28604c36d8245e13ffa4f6d0f6dc32eeac6c6feaf5c08aa06a76b",
          "differometor/simulate.py": "869a0c8465a819ed8f305ede4d14f6e8d5966e8cc6e7cb89ece2a5cd1297468b",
          "differometor/utils.py": "73ee8a862cbc435363904addc363071ed7dc8b1546956f82e1746998fe3b09ff"
        },
        "worker_sha256": "d3c212da0ab1215187407d9cd21dc2cbb5f88dc0b5ee7885135bf7f002d14b58"
      },
      "validated_output_scope": "first_evaluation",
      "warm_metrics": {},
      "worker_error": null
    },
    {
      "artifact_digest": "c4ba2de11c76b49f4b648d3125a34fa342ef96bd269cca1fcdef71e50147af60",
      "artifact_digests": {
        "comparison.json": "15f8d46a404e1eefd7ec83ea4f7f55b145587a2b47fec4fa2c375c044307b5c3",
        "report.json": "76b02a6ba05a72d51617b7d9476e121259514fd03620c4a495052803e5aff832",
        "result": "85fce612aefa8ea569bbea561ce51c49f2294119cd79cdfc82d1c806d4a135f1"
      },
      "candidate_sha": "ea8d294e7198db5cfb549502fa7872d44789da2b",
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
        "comparison_wall_seconds": 0.27985996566712856,
        "peak_rss_bytes": 8353968128,
        "peak_rss_kib": 8158172,
        "total_worker_wall_seconds": 92.74023466371,
        "wall_seconds": 92.46037469804287
      },
      "eligible_full": true,
      "evidence_digest": "a18a40d2d486801b4595db1f7ef42856a00444b5a46ccbcd504d4197519f6a5b",
      "evidence_id": "0ce31ea937834cf48fd2c0b4967aeb58:c4ba2de11c76b49f4b648d3125a34fa342ef96bd269cca1fcdef71e50147af60",
      "execution_status": "completed",
      "issues": [],
      "job_id": "0ce31ea937834cf48fd2c0b4967aeb58",
      "metrics": {
        "compilation": 11.28455969132483,
        "forward": 8.899176081642509,
        "gradient": 1.9146008417010307,
        "peak_rss_bytes": 8353968128,
        "runtime": 10.81493354216218,
        "sensitivity": 0.0008382927626371384,
        "setup": 1.1228294428437948,
        "total": 23.222322676330805,
        "transfer": 0.00031832605600357056
      },
      "phases": {
        "build": 0.8165444768965244,
        "forward": 8.899176081642509,
        "forward_compile": 7.839947385713458,
        "forward_lower": 0.8575513381510973,
        "gradient": 1.9146008417010307,
        "gradient_compile": 1.9346039816737175,
        "gradient_lower": 0.19179905205965042,
        "host_transfer": 0.00031832605600357056,
        "imports": 0.30209931917488575,
        "initialize": 0.002775872126221657,
        "load": 0.0014097746461629868,
        "sensitivity": 0.0008382927626371384,
        "sensitivity_compile": 0.3577008303254843,
        "sensitivity_lower": 0.1029571034014225
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
          "sampled_process_group_peak_rss_bytes": 8355016704,
          "samples": 334
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
          "differometor/simulate.py": "869a0c8465a819ed8f305ede4d14f6e8d5966e8cc6e7cb89ece2a5cd1297468b",
          "differometor/utils.py": "73ee8a862cbc435363904addc363071ed7dc8b1546956f82e1746998fe3b09ff"
        },
        "worker_sha256": "d3c212da0ab1215187407d9cd21dc2cbb5f88dc0b5ee7885135bf7f002d14b58"
      },
      "validated_output_scope": "last_warm_evaluation",
      "warm_metrics": {
        "forward": 8.832825474441051,
        "gradient": 1.8893181793391705,
        "host_transfer": 0.00025085732340812683,
        "sensitivity": 0.18407526426017284
      },
      "worker_error": null
    }
  ],
  "evidence_ids": [
    "bbfbe5f3d20a454d8516163ffea58c7b:3005be8311ae979640c085c30391ead859297cd43a05f84d6082458378556832",
    "0ce31ea937834cf48fd2c0b4967aeb58:c4ba2de11c76b49f4b648d3125a34fa342ef96bd269cca1fcdef71e50147af60"
  ],
  "git_parents": null,
  "heuristic_id": null,
  "hypothesis": null,
  "improved": false,
  "kind": "mutate",
  "lane_id": "tune",
  "metrics": {
    "compilation": 11.28455969132483,
    "forward": 8.899176081642509,
    "gradient": 1.9146008417010307,
    "peak_rss_bytes": 8353968128,
    "runtime": 10.81493354216218,
    "sensitivity": 0.0008382927626371384,
    "setup": 1.1228294428437948,
    "total": 23.222322676330805,
    "transfer": 0.00031832605600357056
  },
  "model_manifest": null,
  "owner": "coordinator",
  "owner_version": 1,
  "parameters": {
    "factor_mode": "off",
    "merge_rhs": true,
    "noise_mode": "broadcast",
    "split_rhs": false
  },
  "parameters_after": {
    "factor_mode": "off",
    "merge_rhs": true,
    "noise_mode": "broadcast",
    "split_rhs": false
  },
  "parameters_before": null,
  "parents": [
    "topology-seed"
  ],
  "prompt_sha256": null,
  "proposal": {
    "candidate_id": "530091c8ae754deb85cc3bdb35699d31",
    "commit_sha": "ea8d294e7198db5cfb549502fa7872d44789da2b",
    "content_sha256": "d52e92a07a86511728d0cc8e48f448726e8deaa0e89e0079e1e2c157f046b1a7",
    "kind": "mutate",
    "lane_id": "tune",
    "parameters": {
      "factor_mode": "off",
      "merge_rhs": true,
      "noise_mode": "broadcast",
      "split_rhs": false
    },
    "parents": [
      "topology-seed"
    ],
    "proposal_id": "530091c8ae754deb85cc3bdb35699d31",
    "provenance": {
      "context": {
        "bytes": 2215,
        "path": "contexts/1cf0bfa1d610c256d73b2fd0c780ffc449e3d26942617b6c2f2ac8cc5ad358c8.json",
        "sha256": "1cf0bfa1d610c256d73b2fd0c780ffc449e3d26942617b6c2f2ac8cc5ad358c8"
      },
      "context_sha256": "7b237dfa0af85bd763bb0a13d768d96b0e22eade9bf03b62a8503d0f3e50f8bb",
      "heuristic_id": "exact-topology-smac-v1",
      "hypothesis": "Measure registered topology parameters under unchanged full correctness checks",
      "model": "SMAC3 random forest + expected improvement",
      "model_calls": 0,
      "model_trained": false,
      "origin": "local-startup",
      "selection_origin": "local-startup",
      "training_configurations": 2
    },
    "recipe": "tune",
    "round_id": "topology-001"
  },
  "proposal_id": "530091c8ae754deb85cc3bdb35699d31",
  "provenance": {
    "context": {
      "bytes": 2215,
      "path": "contexts/1cf0bfa1d610c256d73b2fd0c780ffc449e3d26942617b6c2f2ac8cc5ad358c8.json",
      "sha256": "1cf0bfa1d610c256d73b2fd0c780ffc449e3d26942617b6c2f2ac8cc5ad358c8"
    },
    "context_sha256": "7b237dfa0af85bd763bb0a13d768d96b0e22eade9bf03b62a8503d0f3e50f8bb",
    "heuristic_id": "exact-topology-smac-v1",
    "hypothesis": "Measure registered topology parameters under unchanged full correctness checks",
    "model": "SMAC3 random forest + expected improvement",
    "model_calls": 0,
    "model_trained": false,
    "origin": "local-startup",
    "selection_origin": "local-startup",
    "training_configurations": 2
  },
  "recipe": "tune",
  "response_sha256": null,
  "round_id": "topology-001",
  "target_symbols": null,
  "uncertainty": "No repeat-confirmation or causality is inferred from this export. Inspect exact job evidence and matching cohorts.",
  "valid": true
}
```

### 936f1b7d45c14ffc823c45610b592529

```json
{
  "cohort_digest": "d78b193bdd3e61a0c054f0ba4b2645e67f80f7007e9e5fd6acea817f876795f6",
  "commit_sha": "4e575979c72e42a7a78f2f1aabda9477f6c4c109",
  "content_sha256": "e09b7e4bdc84031b6e88620b5003910c2f0f3f2a8b459fbae9b67437d8beb926",
  "context_sha256": null,
  "evaluation_requests": [
    {
      "attempt": 1,
      "candidate_id": "936f1b7d45c14ffc823c45610b592529",
      "evidence_id": "1b8d66f317c740fa876eccfe0fd2372e:f8c72d105e44c9a2a9ac4d06f6d1c2cef89dc946ed25255c3b0eccec36644512",
      "imported": false,
      "job_id": "1b8d66f317c740fa876eccfe0fd2372e",
      "profile": "screen",
      "request_id": "8618f6950e954797815baa5826eeedba",
      "status": "screen"
    },
    {
      "attempt": 1,
      "candidate_id": "936f1b7d45c14ffc823c45610b592529",
      "evidence_id": "2c21770160cc46239770fce8d5638933:355a713605c5752599403be59ec18612d75aa87339800c90dac495d69f4fb8ed",
      "imported": false,
      "job_id": "2c21770160cc46239770fce8d5638933",
      "profile": "full",
      "request_id": "c9e4c658789346b5900f6cb915cc04a9",
      "status": "valid"
    }
  ],
  "evidence": [
    {
      "artifact_digest": "f8c72d105e44c9a2a9ac4d06f6d1c2cef89dc946ed25255c3b0eccec36644512",
      "artifact_digests": {
        "report.json": "04312db8e30eeb1bb37d68469d6a6e3698035d0e0a4408991589256130bcb228",
        "result": "ce3ba21a5c099c2160004a7bd38055fa1999ddd4a2d701ae01c59a215b3910f7"
      },
      "candidate_sha": "4e575979c72e42a7a78f2f1aabda9477f6c4c109",
      "category": "screen",
      "checks": {
        "official": "not_run",
        "precision": "passed",
        "resource": "passed",
        "source": "passed",
        "strict": "not_run",
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
        "profile": "screen",
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
        "strict_policy": null,
        "worker_sha256": "d3c212da0ab1215187407d9cd21dc2cbb5f88dc0b5ee7885135bf7f002d14b58"
      },
      "cohort_digest": "465a1051caf482041d73c67eca828452830dcc12021b720faaa0f3ab3e41cebb",
      "cost": {
        "peak_rss_bytes": 8311328768,
        "peak_rss_kib": 8116532,
        "total_worker_wall_seconds": 23.876712249591947,
        "wall_seconds": 23.876712249591947
      },
      "eligible_full": false,
      "evidence_digest": "b6b9c6272bd2315dc54ca0ae0e00d314fea819ea47182cccac8dfd2d5a6702c6",
      "evidence_id": "1b8d66f317c740fa876eccfe0fd2372e:f8c72d105e44c9a2a9ac4d06f6d1c2cef89dc946ed25255c3b0eccec36644512",
      "execution_status": "completed",
      "issues": [],
      "job_id": "1b8d66f317c740fa876eccfe0fd2372e",
      "metrics": {
        "compilation": 11.385878350585699,
        "forward": 8.940991543233395,
        "gradient": 1.5818288810551167,
        "peak_rss_bytes": 8311328768,
        "runtime": 10.523975033313036,
        "sensitivity": 0.0008306112140417099,
        "setup": 1.113495372235775,
        "total": 23.02334875613451,
        "transfer": 0.0003239978104829788
      },
      "phases": {
        "build": 0.8085692673921585,
        "forward": 8.940991543233395,
        "forward_compile": 7.883698023855686,
        "forward_lower": 0.8629941735416651,
        "gradient": 1.5818288810551167,
        "gradient_compile": 1.9996591918170452,
        "gradient_lower": 0.19442074373364449,
        "host_transfer": 0.0003239978104829788,
        "imports": 0.3007630202919245,
        "initialize": 0.00275363028049469,
        "load": 0.001409454271197319,
        "sensitivity": 0.0008306112140417099,
        "sensitivity_compile": 0.354710029438138,
        "sensitivity_lower": 0.09039618819952011
      },
      "profile": "screen",
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
          "sampled_process_group_peak_rss_bytes": 8312377344,
          "samples": 86
        }
      },
      "schema_version": "feyer-evolution-evidence-v1",
      "scientific_strike": false,
      "screen_passed": true,
      "source_digests": {
        "clean_diff_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "evaluator_sha256": "2bf4249e453271d1f665c35356485739ad66a9b0327153d678a5b34d81192458",
        "simulator_files_sha256": {
          "differometor/__init__.py": "505d559d5a17409680a91f555882edf23f78cbb7c98ee28845018fa9bfeba7e7",
          "differometor/build.py": "12a5690f48ca736fd9f0bd5301b3b3380a5f9f0b8754cc98781f39c9d413be9b",
          "differometor/components.py": "2e857e19d468d94b46594f71a76221d9d8b677bad05f6cf03b9e57b0e1613593",
          "differometor/plot.py": "16735e0fb14902f2c024e3da9f2655cbea634c4dd9e06c48af1247e12d0cf606",
          "differometor/setups.py": "478b1a7391b28604c36d8245e13ffa4f6d0f6dc32eeac6c6feaf5c08aa06a76b",
          "differometor/simulate.py": "29d1ffcdec52c23fd8e661556fd72ea151ca292b0a7e497ca53a045338c7f6dc",
          "differometor/utils.py": "73ee8a862cbc435363904addc363071ed7dc8b1546956f82e1746998fe3b09ff"
        },
        "worker_sha256": "d3c212da0ab1215187407d9cd21dc2cbb5f88dc0b5ee7885135bf7f002d14b58"
      },
      "validated_output_scope": "first_evaluation",
      "warm_metrics": {},
      "worker_error": null
    },
    {
      "artifact_digest": "355a713605c5752599403be59ec18612d75aa87339800c90dac495d69f4fb8ed",
      "artifact_digests": {
        "comparison.json": "53db6296074a20f8e3e7d78deadfb85143c844ea4844432e77356e1aabd3110c",
        "report.json": "e6015e6f49bd0fae3044cec3232b387423c2503ec02d264b6a6cdd01717e8df6",
        "result": "f7497cae07b23e52ae08c841a6508844ddab0a77e8a68cae6f436f587711096b"
      },
      "candidate_sha": "4e575979c72e42a7a78f2f1aabda9477f6c4c109",
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
        "comparison_wall_seconds": 0.2796126753091812,
        "peak_rss_bytes": 8312143872,
        "peak_rss_kib": 8117328,
        "total_worker_wall_seconds": 91.71198118105531,
        "wall_seconds": 91.43236850574613
      },
      "eligible_full": true,
      "evidence_digest": "6722d603f7f3c261c015121add9cf2836bcc22e78f75e269684252c2d4cc878f",
      "evidence_id": "2c21770160cc46239770fce8d5638933:355a713605c5752599403be59ec18612d75aa87339800c90dac495d69f4fb8ed",
      "execution_status": "completed",
      "issues": [],
      "job_id": "2c21770160cc46239770fce8d5638933",
      "metrics": {
        "compilation": 11.358388669788837,
        "forward": 8.909868536517024,
        "gradient": 1.5828159358352423,
        "peak_rss_bytes": 8312143872,
        "runtime": 10.493826411664486,
        "sensitivity": 0.0008176527917385101,
        "setup": 1.129514530301094,
        "total": 22.981729611754417,
        "transfer": 0.0003242865204811096
      },
      "phases": {
        "build": 0.8240314479917288,
        "forward": 8.909868536517024,
        "forward_compile": 7.8336861822754145,
        "forward_lower": 0.8589822724461555,
        "gradient": 1.5828159358352423,
        "gradient_compile": 2.011961195617914,
        "gradient_lower": 0.19459065236151218,
        "host_transfer": 0.0003242865204811096,
        "imports": 0.30131642520427704,
        "initialize": 0.0027533210813999176,
        "load": 0.0014133360236883163,
        "sensitivity": 0.0008176527917385101,
        "sensitivity_compile": 0.3596100267022848,
        "sensitivity_lower": 0.09955834038555622
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
          "sampled_process_group_peak_rss_bytes": 8313192448,
          "samples": 330
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
          "differometor/simulate.py": "29d1ffcdec52c23fd8e661556fd72ea151ca292b0a7e497ca53a045338c7f6dc",
          "differometor/utils.py": "73ee8a862cbc435363904addc363071ed7dc8b1546956f82e1746998fe3b09ff"
        },
        "worker_sha256": "d3c212da0ab1215187407d9cd21dc2cbb5f88dc0b5ee7885135bf7f002d14b58"
      },
      "validated_output_scope": "last_warm_evaluation",
      "warm_metrics": {
        "forward": 9.35409595258534,
        "gradient": 1.5796831268817186,
        "host_transfer": 0.0002336353063583374,
        "sensitivity": 0.1786789894104004
      },
      "worker_error": null
    }
  ],
  "evidence_ids": [
    "1b8d66f317c740fa876eccfe0fd2372e:f8c72d105e44c9a2a9ac4d06f6d1c2cef89dc946ed25255c3b0eccec36644512",
    "2c21770160cc46239770fce8d5638933:355a713605c5752599403be59ec18612d75aa87339800c90dac495d69f4fb8ed"
  ],
  "git_parents": null,
  "heuristic_id": null,
  "hypothesis": null,
  "improved": false,
  "kind": "mutate",
  "lane_id": "tune",
  "metrics": {
    "compilation": 11.358388669788837,
    "forward": 8.909868536517024,
    "gradient": 1.5828159358352423,
    "peak_rss_bytes": 8312143872,
    "runtime": 10.493826411664486,
    "sensitivity": 0.0008176527917385101,
    "setup": 1.129514530301094,
    "total": 22.981729611754417,
    "transfer": 0.0003242865204811096
  },
  "model_manifest": null,
  "owner": "coordinator",
  "owner_version": 1,
  "parameters": {
    "factor_mode": "direct",
    "merge_rhs": true,
    "noise_mode": "broadcast",
    "split_rhs": false
  },
  "parameters_after": {
    "factor_mode": "direct",
    "merge_rhs": true,
    "noise_mode": "broadcast",
    "split_rhs": false
  },
  "parameters_before": null,
  "parents": [
    "topology-seed"
  ],
  "prompt_sha256": null,
  "proposal": {
    "candidate_id": "936f1b7d45c14ffc823c45610b592529",
    "commit_sha": "4e575979c72e42a7a78f2f1aabda9477f6c4c109",
    "content_sha256": "e09b7e4bdc84031b6e88620b5003910c2f0f3f2a8b459fbae9b67437d8beb926",
    "kind": "mutate",
    "lane_id": "tune",
    "parameters": {
      "factor_mode": "direct",
      "merge_rhs": true,
      "noise_mode": "broadcast",
      "split_rhs": false
    },
    "parents": [
      "topology-seed"
    ],
    "proposal_id": "936f1b7d45c14ffc823c45610b592529",
    "provenance": {
      "context": {
        "bytes": 2547,
        "path": "contexts/47c524f50c7253db1fe7414cb6eb53510a4c1400171becef77dcaaf6b1d25e4e.json",
        "sha256": "47c524f50c7253db1fe7414cb6eb53510a4c1400171becef77dcaaf6b1d25e4e"
      },
      "context_sha256": "d6bce927b4fcc8ba3443a7bb880864b4c7b5579f60c4614421df9bfd49984d6e",
      "heuristic_id": "exact-topology-smac-v1",
      "hypothesis": "Measure registered topology parameters under unchanged full correctness checks",
      "model": "SMAC3 random forest + expected improvement",
      "model_calls": 0,
      "model_trained": false,
      "origin": "local-startup",
      "selection_origin": "local-startup",
      "training_configurations": 3
    },
    "recipe": "tune",
    "round_id": "topology-001"
  },
  "proposal_id": "936f1b7d45c14ffc823c45610b592529",
  "provenance": {
    "context": {
      "bytes": 2547,
      "path": "contexts/47c524f50c7253db1fe7414cb6eb53510a4c1400171becef77dcaaf6b1d25e4e.json",
      "sha256": "47c524f50c7253db1fe7414cb6eb53510a4c1400171becef77dcaaf6b1d25e4e"
    },
    "context_sha256": "d6bce927b4fcc8ba3443a7bb880864b4c7b5579f60c4614421df9bfd49984d6e",
    "heuristic_id": "exact-topology-smac-v1",
    "hypothesis": "Measure registered topology parameters under unchanged full correctness checks",
    "model": "SMAC3 random forest + expected improvement",
    "model_calls": 0,
    "model_trained": false,
    "origin": "local-startup",
    "selection_origin": "local-startup",
    "training_configurations": 3
  },
  "recipe": "tune",
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
| 1 | campaign_initialized | coordinator | {"spec_digest": "c5df55b766c3509dbd4b44bf174ee8bb8776d1f0731be0243569ac1af9828882"} |
| 2 | owner_claimed | coordinator | {"actor": "coordinator", "role": "coordinator", "version": 1} |
| 3 | round_created | coordinator | {"round_id": "topology-001", "spec_digest": "3f0f3ed646e039f42d42286ac395d07432baf74ff9eac3701851199879a37f8b", "version": 1} |
| 4 | candidate_proposed | coordinator | {"candidate_id": "topology-seed", "duplicate_of": null, "owner_version": 1, "proposal_digest": "c10c852a613fa75daf6c0a567d54f484a96669662ff462b364fda0246db8abe7", "proposal_id": "topology-seed"} |
| 5 | evidence_observed | coordinator | {"candidate_id": "topology-seed", "category": "valid", "evidence_digest": "764d7519b0a043491380335c9d5241917c2cd7f6e1bb77b25ab9893dfc62d2f6", "evidence_id": "be32d82593f043489d653a13f6e2694a:c6345924647cc627855ee6d3ee1a14b13eaf26fde6952a2277cef3f5046101b9", "job_id": "be32d82593f043489d653a13f6e2694a", "progress": null, "status": "valid", "strikes": 0} |
| 6 | decision_recorded | coordinator | {"decision_id": "3b5b664306504c809e532536e5e8b57a", "payload": {"context": {"bytes": 1886, "path": "contexts/aef6e9e8dfdcf2c69d481cc61336979b9d0f225d52855c3e780338ed18ecb854.json", "sha256": "aef6e9e8dfdcf2c69d481cc61336979b9d0f225d52855c3e780338ed18ecb854"}, "model_trained": false, "origin": "local-startup", "selection_origin": "local-startup", "training_configurations": 1}, "payload_digest": "f21480444689ad43f94d601fbd77bbaafe8143fb56013cf033e87c6aadccceb3"} |
| 7 | candidate_proposed | coordinator | {"candidate_id": "3b5b664306504c809e532536e5e8b57a", "duplicate_of": null, "owner_version": 1, "proposal_digest": "f3862682eb6be8e805aa6b1300fef1e6e6abe7259aa8bab8ad7fd446394c2fc0", "proposal_id": "3b5b664306504c809e532536e5e8b57a"} |
| 8 | evaluation_reserved | coordinator | {"attempt": 1, "candidate_id": "3b5b664306504c809e532536e5e8b57a", "profile": "screen", "request_id": "6a9ea2bb79154fbfbb0d2946c6320ae1"} |
| 9 | evaluation_bound | coordinator | {"job_id": "335506602662421987d0b851acf3d593", "request_id": "6a9ea2bb79154fbfbb0d2946c6320ae1"} |
| 10 | evidence_observed | coordinator | {"candidate_id": "3b5b664306504c809e532536e5e8b57a", "category": "screen", "evidence_digest": "34e79ba5029dea327f4ccf40546bd049ef3fb7df2897a750cebf00825ecff907", "evidence_id": "335506602662421987d0b851acf3d593:74d94f798c1cfa797259c64b1bba4b07b4b37554c2b1aa823af6af675a89bc12", "job_id": "335506602662421987d0b851acf3d593", "progress": null, "status": "screened", "strikes": 0} |
| 11 | evaluation_reserved | coordinator | {"attempt": 1, "candidate_id": "3b5b664306504c809e532536e5e8b57a", "profile": "full", "request_id": "faebcace3e244e358d75006fe690e318"} |
| 12 | evaluation_bound | coordinator | {"job_id": "67de6c4aaf024c959b71352e7e54339b", "request_id": "faebcace3e244e358d75006fe690e318"} |
| 13 | evidence_observed | coordinator | {"candidate_id": "3b5b664306504c809e532536e5e8b57a", "category": "valid", "evidence_digest": "80262ede0002a95be7d63e8e37885f18e58b63286f08f0cef3b01ec68322e58f", "evidence_id": "67de6c4aaf024c959b71352e7e54339b:c5a039f8f44ebd6fde56c5d65f9ffbcdb9510342d377312270fbce2fd819eec5", "job_id": "67de6c4aaf024c959b71352e7e54339b", "progress": {"axes": ["setup", "compilation", "forward", "sensitivity", "gradient", "transfer"], "meaningful_pareto": false, "meaningful_total": false, "policy": {"absolute": 0.02, "relative": 0.01}, "reference_best_total": 22.790136247873306, "reference_parents": ["topology-seed"]}, "status": "valid", "strikes": 1} |
| 14 | decision_recorded | coordinator | {"decision_id": "530091c8ae754deb85cc3bdb35699d31", "payload": {"context": {"bytes": 2215, "path": "contexts/1cf0bfa1d610c256d73b2fd0c780ffc449e3d26942617b6c2f2ac8cc5ad358c8.json", "sha256": "1cf0bfa1d610c256d73b2fd0c780ffc449e3d26942617b6c2f2ac8cc5ad358c8"}, "model_trained": false, "origin": "local-startup", "selection_origin": "local-startup", "training_configurations": 2}, "payload_digest": "7d119792385a8ad873ba00a0102cdc45155ad315a4dce0c4a7bded97f577a234"} |
| 15 | candidate_proposed | coordinator | {"candidate_id": "530091c8ae754deb85cc3bdb35699d31", "duplicate_of": null, "owner_version": 1, "proposal_digest": "538c42e9bc5217a69347406c8c89ae8e5599f02646ad8086288837a7abcff7ce", "proposal_id": "530091c8ae754deb85cc3bdb35699d31"} |
| 16 | evaluation_reserved | coordinator | {"attempt": 1, "candidate_id": "530091c8ae754deb85cc3bdb35699d31", "profile": "screen", "request_id": "8a30968d281141d69d107ffe7b793ff5"} |
| 17 | evaluation_bound | coordinator | {"job_id": "bbfbe5f3d20a454d8516163ffea58c7b", "request_id": "8a30968d281141d69d107ffe7b793ff5"} |
| 18 | evidence_observed | coordinator | {"candidate_id": "530091c8ae754deb85cc3bdb35699d31", "category": "screen", "evidence_digest": "6d04d018831b0907c67a84523ccae909acbb495ce0d0dff7502549d10644b698", "evidence_id": "bbfbe5f3d20a454d8516163ffea58c7b:3005be8311ae979640c085c30391ead859297cd43a05f84d6082458378556832", "job_id": "bbfbe5f3d20a454d8516163ffea58c7b", "progress": null, "status": "screened", "strikes": 1} |
| 19 | evaluation_reserved | coordinator | {"attempt": 1, "candidate_id": "530091c8ae754deb85cc3bdb35699d31", "profile": "full", "request_id": "c748ce60974b4743a4711db3bfee3bb1"} |
| 20 | evaluation_bound | coordinator | {"job_id": "0ce31ea937834cf48fd2c0b4967aeb58", "request_id": "c748ce60974b4743a4711db3bfee3bb1"} |
| 21 | evidence_observed | coordinator | {"candidate_id": "530091c8ae754deb85cc3bdb35699d31", "category": "valid", "evidence_digest": "c23e67a1ed5063636aca7c2c758323b863b607e429326fb5f027c6e5af6f9dbe", "evidence_id": "0ce31ea937834cf48fd2c0b4967aeb58:c4ba2de11c76b49f4b648d3125a34fa342ef96bd269cca1fcdef71e50147af60", "job_id": "0ce31ea937834cf48fd2c0b4967aeb58", "progress": {"axes": ["setup", "compilation", "forward", "sensitivity", "gradient", "transfer"], "meaningful_pareto": false, "meaningful_total": false, "policy": {"absolute": 0.02, "relative": 0.01}, "reference_best_total": 22.790136247873306, "reference_parents": ["topology-seed"]}, "status": "valid", "strikes": 2} |
| 22 | decision_recorded | coordinator | {"decision_id": "936f1b7d45c14ffc823c45610b592529", "payload": {"context": {"bytes": 2547, "path": "contexts/47c524f50c7253db1fe7414cb6eb53510a4c1400171becef77dcaaf6b1d25e4e.json", "sha256": "47c524f50c7253db1fe7414cb6eb53510a4c1400171becef77dcaaf6b1d25e4e"}, "model_trained": false, "origin": "local-startup", "selection_origin": "local-startup", "training_configurations": 3}, "payload_digest": "1364506a9bcc3179eff68149c960bda06c90b8005c4ad8377a53f067070ac4a7"} |
| 23 | candidate_proposed | coordinator | {"candidate_id": "936f1b7d45c14ffc823c45610b592529", "duplicate_of": null, "owner_version": 1, "proposal_digest": "391b2a305da6eb4dd39d52b8910aae5998af6837ecdc6481faaad6fa91913841", "proposal_id": "936f1b7d45c14ffc823c45610b592529"} |
| 24 | evaluation_reserved | coordinator | {"attempt": 1, "candidate_id": "936f1b7d45c14ffc823c45610b592529", "profile": "screen", "request_id": "8618f6950e954797815baa5826eeedba"} |
| 25 | evaluation_bound | coordinator | {"job_id": "1b8d66f317c740fa876eccfe0fd2372e", "request_id": "8618f6950e954797815baa5826eeedba"} |
| 26 | evidence_observed | coordinator | {"candidate_id": "936f1b7d45c14ffc823c45610b592529", "category": "screen", "evidence_digest": "5f9b22118739c0ab50e2c3445e823f5f241ba4373a66bd17a2bcb4ed36b3a9e0", "evidence_id": "1b8d66f317c740fa876eccfe0fd2372e:f8c72d105e44c9a2a9ac4d06f6d1c2cef89dc946ed25255c3b0eccec36644512", "job_id": "1b8d66f317c740fa876eccfe0fd2372e", "progress": null, "status": "screened", "strikes": 2} |
| 27 | evaluation_reserved | coordinator | {"attempt": 1, "candidate_id": "936f1b7d45c14ffc823c45610b592529", "profile": "full", "request_id": "c9e4c658789346b5900f6cb915cc04a9"} |
| 28 | evaluation_bound | coordinator | {"job_id": "2c21770160cc46239770fce8d5638933", "request_id": "c9e4c658789346b5900f6cb915cc04a9"} |
| 29 | evidence_observed | coordinator | {"candidate_id": "936f1b7d45c14ffc823c45610b592529", "category": "valid", "evidence_digest": "0c78212f13fa434872cfdcdea97f4e59dddd51210fa63f28bb0d9d3e0de9f14a", "evidence_id": "2c21770160cc46239770fce8d5638933:355a713605c5752599403be59ec18612d75aa87339800c90dac495d69f4fb8ed", "job_id": "2c21770160cc46239770fce8d5638933", "progress": {"axes": ["setup", "compilation", "forward", "sensitivity", "gradient", "transfer"], "meaningful_pareto": false, "meaningful_total": false, "policy": {"absolute": 0.02, "relative": 0.01}, "reference_best_total": 22.790136247873306, "reference_parents": ["topology-seed"]}, "status": "valid", "strikes": 3} |
| 30 | decision_recorded | coordinator | {"decision_id": "8242aaa71c8d44529fc29c9b06786d14", "payload": {"acquisition_rank": 1, "acquisition_score": 0.008990157453494824, "context": {"bytes": 3663, "path": "contexts/971f864e90c102b9458f4853f59963722033533d0abc69c86337d0f784530a2c.json", "sha256": "971f864e90c102b9458f4853f59963722033533d0abc69c86337d0f784530a2c"}, "model_trained": true, "origin": "Acquisition Function Maximizer: Exact Topology Menu", "ranked_options": [{"parameters": {"factor_mode": "off", "merge_rhs": false, "noise_mode": "shared", "split_rhs": true}, "rank": 1, "score": 0.008990157453494824}, {"parameters": {"factor_mode": "off", "merge_rhs": true, "noise_mode": "shared", "split_rhs": false}, "rank": 2, "score… [full detail in events.jsonl] |

Guidance may propose a new round. It cannot silently replace frozen operators, ownership, evaluation requirements or budgets. Only the coordinator can admit that round through the campaign state API. Publishing this ledger does not merge or promote candidate code.
