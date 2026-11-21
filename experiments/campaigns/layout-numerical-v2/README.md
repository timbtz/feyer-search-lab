# Campaign layout-numerical-v2

Export schema: `feyer-campaign-export-v1`. Snapshot: `75af823ce9237c6bbe51f70ceb4b0f0ee5a70708027bdf1faa226a8ffbbed39b`.

[Frozen proposer context](contexts/b15f119588493165b17d2375b5148f6e92c205c2e5a657fe18a3ca011c1bcb33.json) — SHA256 `b15f119588493165b17d2375b5148f6e92c205c2e5a657fe18a3ca011c1bcb33`.

This is an evidence ledger. Scientific parents describe chosen inputs to an experiment; they are not necessarily Git parents. Phase changes are observations, not proof that one edit caused the difference. A failed attempt remains part of the history.

## Ownership and frozen policy

Campaign specification digest: `7120f76767786f83b48bfe836708a978efb09e140b2fc4e29fd70334b159ebae`.

| Actor | Role | Ownership version | Active |
| --- | --- | --- | --- |
| coordinator | coordinator | 1 | True |

## Scientific lineage

Edges come from declared scientific parents, not inferred chronology or Git ancestry.

```mermaid
graph LR
  n0["topology-seed seed valid"]
  n1["7a6936e264024fc7a629cbc5e75ec8d3 mutate valid"]
  n2["f28325fb234141beb0f0054e7161f709 mutate valid"]
  n0 -->|mutate| n1
  n1 -->|mutate| n2
```

## Candidate outcomes

| Candidate | Round / lane | Scientific parents | Exact commit | State | First-run seconds | Evidence IDs |
| --- | --- | --- | --- | --- | --- | --- |
| topology-seed | topology-001 / tune | root | e0a1dc69f4951c100fefbc9fc08a23c3c12058dc | valid | 21.9847 | d07456c28e8647289ddf32fd9676bf0d:acb6f2e3adb36a5a0d76489a61f11270265d6e92d3833b7e9241808a32cbd21d |
| 7a6936e264024fc7a629cbc5e75ec8d3 | topology-001 / tune | topology-seed | 8427aae28bd8bb2b248e833fa416ce0563d53c9e | valid | 21.8678 | 955f9c9b082c4cb8a74af964baa7290c:46c75f8de93ce199d794f52f5ab3de4c5af0de4bc6ecef00ca8993aae2dc85f7, 48775628352f423f9d4dbe90af6b54e8:32e35e2148292f98536c412ddcb655a7d61881911219c76647d34b4ffb24ca29 |
| f28325fb234141beb0f0054e7161f709 | topology-001 / tune | 7a6936e264024fc7a629cbc5e75ec8d3 | 3a2073ad5add8770eab0d37b55ad67cea71b448b | valid | 21.1998 | 004ac1572615488caf91628b849da147:e23d4ea50664b359224f93998019b986ccb3065f06f7e7179f7244a929e263bc, d9a90c7ee1974e64a4aebcef47572111:38345588a583bc5d8e10c81e4a51b2a962c05ec4147010931203b6e8b7f3a836 |

## Round decisions and stalled work

### Round topology-001

Frozen specification: `a998fa82854524d2d6272100fdc7817495162e4b5af51b45dd113f04b3d46d1d`; version: 1; closed: False.

```json
{
  "budget": {
    "deadline_unix": 1795296029.2574458,
    "max_evaluations": 38,
    "max_model_calls": 0,
    "max_proposals": 5
  },
  "dimensions": {
    "factor_mode": [
      "off",
      "direct"
    ],
    "noise_mode": [
      "broadcast",
      "shared"
    ]
  },
  "lanes": {
    "tune": {
      "dimensions": [
        "noise_mode",
        "factor_mode"
      ],
      "max_proposals": 4,
      "owner": "coordinator",
      "stall_limit": 4
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
        "factor_mode"
      ]
    }
  },
  "round_id": "topology-001",
  "seed_parameters": {
    "factor_mode": "off",
    "noise_mode": "broadcast"
  }
}
```

- topology-001/tune: ready; owner coordinator; strikes 0; reason not recorded

## Candidate evidence and proposed changes

### topology-seed

```json
{
  "cohort_digest": "10567ad0f8dcb7122b6b182e1be342313b89eef340d4070073fdf62d6342204c",
  "commit_sha": "e0a1dc69f4951c100fefbc9fc08a23c3c12058dc",
  "content_sha256": "fddf0e980eeabeda7f59782b59f9cb44487a2545dc84918de8359d3fddca1918",
  "context_sha256": null,
  "evaluation_requests": [
    {
      "attempt": 1,
      "candidate_id": "topology-seed",
      "evidence_id": "d07456c28e8647289ddf32fd9676bf0d:acb6f2e3adb36a5a0d76489a61f11270265d6e92d3833b7e9241808a32cbd21d",
      "imported": true,
      "job_id": "d07456c28e8647289ddf32fd9676bf0d",
      "profile": "full",
      "request_id": "a0a1ff79ad064015b84cac0328c822b6",
      "status": "valid"
    }
  ],
  "evidence": [
    {
      "artifact_digest": "acb6f2e3adb36a5a0d76489a61f11270265d6e92d3833b7e9241808a32cbd21d",
      "artifact_digests": {
        "comparison.json": "15f8d46a404e1eefd7ec83ea4f7f55b145587a2b47fec4fa2c375c044307b5c3",
        "report.json": "f47dd4e698be534adf135e5449fbc78f49850dfa52b95ede5aadef6148ced1fe",
        "result": "d0013c13f5dd4b972e69f5d579cffc98ec5f25a1f20d1b2d7993ff1abaa0762e"
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
          "budget_bytes": 32000000000,
          "enforcement": "sampled_process_group_rss",
          "kernel_memory_limit_enforced": false
        },
        "profile": "full",
        "protected_baseline_sha": "02ec741d8a1bf1a2278294ea74f9fc1d68f08f1f",
        "signature": {
          "environment": {
            "backend": "cpu",
            "cpu_affinity_ids": [
              2
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
      "cohort_digest": "10567ad0f8dcb7122b6b182e1be342313b89eef340d4070073fdf62d6342204c",
      "cost": {
        "comparison_wall_seconds": 0.2645955327898264,
        "peak_rss_bytes": 8348561408,
        "peak_rss_kib": 8152892,
        "total_worker_wall_seconds": 86.0789197050035,
        "wall_seconds": 85.81432417221367
      },
      "eligible_full": true,
      "evidence_digest": "7fb9123d5959286ed58df69e142289ebad13ef9d50e2092629aa817e19de815f",
      "evidence_id": "d07456c28e8647289ddf32fd9676bf0d:acb6f2e3adb36a5a0d76489a61f11270265d6e92d3833b7e9241808a32cbd21d",
      "execution_status": "completed",
      "issues": [],
      "job_id": "d07456c28e8647289ddf32fd9676bf0d",
      "metrics": {
        "compilation": 10.914647668600082,
        "forward": 8.24197961203754,
        "gradient": 1.7220865543931723,
        "peak_rss_bytes": 8348561408,
        "runtime": 9.965275375172496,
        "sensitivity": 0.0008697714656591415,
        "setup": 1.104821676388383,
        "total": 21.98474472016096,
        "transfer": 0.0003394372761249542
      },
      "phases": {
        "build": 0.8110483679920435,
        "forward": 8.24197961203754,
        "forward_compile": 7.634304258972406,
        "forward_lower": 0.8239494990557432,
        "gradient": 1.7220865543931723,
        "gradient_compile": 1.899645121768117,
        "gradient_lower": 0.18131746165454388,
        "host_transfer": 0.0003394372761249542,
        "imports": 0.28936965577304363,
        "initialize": 0.0029201582074165344,
        "load": 0.0014834944158792496,
        "sensitivity": 0.0008697714656591415,
        "sensitivity_compile": 0.28414630331099033,
        "sensitivity_lower": 0.09128502383828163
      },
      "profile": "full",
      "resource_evidence": {
        "budget_bytes": 32000000000,
        "container_limits": {
          "cpu.max": "1600000 100000",
          "cpuset.cpus.effective": "0-127",
          "memory.max": "59055800320",
          "memory.swap.max": "0"
        },
        "limitation": "Sampled process-group RSS is not a kernel-enforced memory cap.",
        "memory_monitoring": {
          "budget_bytes": 32000000000,
          "enforcement": "sampled_process_group_rss",
          "exceeded": false,
          "kernel_memory_limit_enforced": false,
          "notes": "RSS sampling can miss brief peaks and counts shared pages in each process. It excludes GPU VRAM and does not reserve RAM or constrain other instance work.",
          "sampled_process_group_peak_rss_bytes": 8349609984,
          "samples": 327
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
        "forward": 8.690181551501155,
        "gradient": 1.7248577270656824,
        "host_transfer": 0.00021371990442276,
        "sensitivity": 0.1098624337464571
      },
      "worker_error": null
    }
  ],
  "evidence_ids": [
    "d07456c28e8647289ddf32fd9676bf0d:acb6f2e3adb36a5a0d76489a61f11270265d6e92d3833b7e9241808a32cbd21d"
  ],
  "git_parents": null,
  "heuristic_id": null,
  "hypothesis": null,
  "improved": false,
  "kind": "seed",
  "lane_id": "tune",
  "metrics": {
    "compilation": 10.914647668600082,
    "forward": 8.24197961203754,
    "gradient": 1.7220865543931723,
    "peak_rss_bytes": 8348561408,
    "runtime": 9.965275375172496,
    "sensitivity": 0.0008697714656591415,
    "setup": 1.104821676388383,
    "total": 21.98474472016096,
    "transfer": 0.0003394372761249542
  },
  "model_manifest": null,
  "owner": "coordinator",
  "owner_version": 1,
  "parameters": {
    "factor_mode": "off",
    "noise_mode": "broadcast"
  },
  "parameters_after": {
    "factor_mode": "off",
    "noise_mode": "broadcast"
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
      "noise_mode": "broadcast"
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

### 7a6936e264024fc7a629cbc5e75ec8d3

```json
{
  "cohort_digest": "10567ad0f8dcb7122b6b182e1be342313b89eef340d4070073fdf62d6342204c",
  "commit_sha": "8427aae28bd8bb2b248e833fa416ce0563d53c9e",
  "content_sha256": "151c29a4b285ee3987696bf8adc9dd02f1dc7a0fe518a59d1f5bbbc0298103d7",
  "context_sha256": null,
  "evaluation_requests": [
    {
      "attempt": 1,
      "candidate_id": "7a6936e264024fc7a629cbc5e75ec8d3",
      "evidence_id": "955f9c9b082c4cb8a74af964baa7290c:46c75f8de93ce199d794f52f5ab3de4c5af0de4bc6ecef00ca8993aae2dc85f7",
      "imported": false,
      "job_id": "955f9c9b082c4cb8a74af964baa7290c",
      "profile": "screen",
      "request_id": "2c5df883c5fe485389887f918de84941",
      "status": "screen"
    },
    {
      "attempt": 1,
      "candidate_id": "7a6936e264024fc7a629cbc5e75ec8d3",
      "evidence_id": "48775628352f423f9d4dbe90af6b54e8:32e35e2148292f98536c412ddcb655a7d61881911219c76647d34b4ffb24ca29",
      "imported": false,
      "job_id": "48775628352f423f9d4dbe90af6b54e8",
      "profile": "full",
      "request_id": "7018c7f78f9d4aa1b86189afcbe615c5",
      "status": "valid"
    }
  ],
  "evidence": [
    {
      "artifact_digest": "46c75f8de93ce199d794f52f5ab3de4c5af0de4bc6ecef00ca8993aae2dc85f7",
      "artifact_digests": {
        "report.json": "2702ec91f4d31e7a0d30bb3aa6829244c1bfb5035e36c003bce45f343c8cb31a",
        "result": "a0279cb44c48db84c3b4aab88718c34801768baa2067e311c52a71691c410fae"
      },
      "candidate_sha": "8427aae28bd8bb2b248e833fa416ce0563d53c9e",
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
          "budget_bytes": 32000000000,
          "enforcement": "sampled_process_group_rss",
          "kernel_memory_limit_enforced": false
        },
        "profile": "screen",
        "protected_baseline_sha": "02ec741d8a1bf1a2278294ea74f9fc1d68f08f1f",
        "signature": {
          "environment": {
            "backend": "cpu",
            "cpu_affinity_ids": [
              2
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
      "cohort_digest": "fc9228f32197f0d2653ba0de06fc01d528953444ab2039dbff6e1284cf689351",
      "cost": {
        "peak_rss_bytes": 7435919360,
        "peak_rss_kib": 7261640,
        "total_worker_wall_seconds": 23.096561200916767,
        "wall_seconds": 23.096561200916767
      },
      "eligible_full": false,
      "evidence_digest": "984f519708ef68e2f3bc91669d550128266b739681e9d5b9d9551a874ea06ff8",
      "evidence_id": "955f9c9b082c4cb8a74af964baa7290c:46c75f8de93ce199d794f52f5ab3de4c5af0de4bc6ecef00ca8993aae2dc85f7",
      "execution_status": "completed",
      "issues": [],
      "job_id": "955f9c9b082c4cb8a74af964baa7290c",
      "metrics": {
        "compilation": 11.075810870155692,
        "forward": 8.337347747758031,
        "gradient": 1.45272121950984,
        "peak_rss_bytes": 7435919360,
        "runtime": 9.791459495201707,
        "sensitivity": 0.0010609906166791916,
        "setup": 1.122118839994073,
        "total": 21.989389205351472,
        "transfer": 0.0003295373171567917
      },
      "phases": {
        "build": 0.824949337169528,
        "forward": 8.337347747758031,
        "forward_compile": 7.590141041204333,
        "forward_lower": 0.8203413467854261,
        "gradient": 1.45272121950984,
        "gradient_compile": 1.9606192968785763,
        "gradient_lower": 0.20317108742892742,
        "host_transfer": 0.0003295373171567917,
        "imports": 0.2928202785551548,
        "initialize": 0.0029417891055345535,
        "load": 0.0014074351638555527,
        "sensitivity": 0.0010609906166791916,
        "sensitivity_compile": 0.3998064957559109,
        "sensitivity_lower": 0.10173160210251808
      },
      "profile": "screen",
      "resource_evidence": {
        "budget_bytes": 32000000000,
        "container_limits": {
          "cpu.max": "1600000 100000",
          "cpuset.cpus.effective": "0-127",
          "memory.max": "59055800320",
          "memory.swap.max": "0"
        },
        "limitation": "Sampled process-group RSS is not a kernel-enforced memory cap.",
        "memory_monitoring": {
          "budget_bytes": 32000000000,
          "enforcement": "sampled_process_group_rss",
          "exceeded": false,
          "kernel_memory_limit_enforced": false,
          "notes": "RSS sampling can miss brief peaks and counts shared pages in each process. It excludes GPU VRAM and does not reserve RAM or constrain other instance work.",
          "sampled_process_group_peak_rss_bytes": 7436967936,
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
          "differometor/simulate.py": "821227035235395214cdd4bd7f793b99958d08d05709ac3dbd8ba2841abc83b6",
          "differometor/utils.py": "73ee8a862cbc435363904addc363071ed7dc8b1546956f82e1746998fe3b09ff"
        },
        "worker_sha256": "d3c212da0ab1215187407d9cd21dc2cbb5f88dc0b5ee7885135bf7f002d14b58"
      },
      "validated_output_scope": "first_evaluation",
      "warm_metrics": {},
      "worker_error": null
    },
    {
      "artifact_digest": "32e35e2148292f98536c412ddcb655a7d61881911219c76647d34b4ffb24ca29",
      "artifact_digests": {
        "comparison.json": "53db6296074a20f8e3e7d78deadfb85143c844ea4844432e77356e1aabd3110c",
        "report.json": "c2079b88e9393bc383132107daea97da09efe1e6321707ad4dc9374ed9c59804",
        "result": "4a8842a53c9d679b12f9493bf132ed9656bbbba743aba9d9e86db7fdf4fecf94"
      },
      "candidate_sha": "8427aae28bd8bb2b248e833fa416ce0563d53c9e",
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
          "budget_bytes": 32000000000,
          "enforcement": "sampled_process_group_rss",
          "kernel_memory_limit_enforced": false
        },
        "profile": "full",
        "protected_baseline_sha": "02ec741d8a1bf1a2278294ea74f9fc1d68f08f1f",
        "signature": {
          "environment": {
            "backend": "cpu",
            "cpu_affinity_ids": [
              2
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
      "cohort_digest": "10567ad0f8dcb7122b6b182e1be342313b89eef340d4070073fdf62d6342204c",
      "cost": {
        "comparison_wall_seconds": 0.2649079393595457,
        "peak_rss_bytes": 7439167488,
        "peak_rss_kib": 7264812,
        "total_worker_wall_seconds": 85.43080324679613,
        "wall_seconds": 85.16589530743659
      },
      "eligible_full": true,
      "evidence_digest": "f3c6ed7da367d7792effe6974f788d598e223a18208c020a00ec361bdf888cdd",
      "evidence_id": "48775628352f423f9d4dbe90af6b54e8:32e35e2148292f98536c412ddcb655a7d61881911219c76647d34b4ffb24ca29",
      "execution_status": "completed",
      "issues": [],
      "job_id": "48775628352f423f9d4dbe90af6b54e8",
      "metrics": {
        "compilation": 10.998526081442833,
        "forward": 8.333781151100993,
        "gradient": 1.432364558801055,
        "peak_rss_bytes": 7439167488,
        "runtime": 9.767398297786713,
        "sensitivity": 0.0009126197546720505,
        "setup": 1.1018755566328764,
        "total": 21.867799935862422,
        "transfer": 0.00033996812999248505
      },
      "phases": {
        "build": 0.8074235953390598,
        "forward": 8.333781151100993,
        "forward_compile": 7.629685152322054,
        "forward_lower": 0.823846148326993,
        "gradient": 1.432364558801055,
        "gradient_compile": 1.9815922733396292,
        "gradient_lower": 0.19165615923702717,
        "host_transfer": 0.00033996812999248505,
        "imports": 0.2901510000228882,
        "initialize": 0.0028965286910533905,
        "load": 0.0014044325798749924,
        "sensitivity": 0.0009126197546720505,
        "sensitivity_compile": 0.2899557910859585,
        "sensitivity_lower": 0.08179055713117123
      },
      "profile": "full",
      "resource_evidence": {
        "budget_bytes": 32000000000,
        "container_limits": {
          "cpu.max": "1600000 100000",
          "cpuset.cpus.effective": "0-127",
          "memory.max": "59055800320",
          "memory.swap.max": "0"
        },
        "limitation": "Sampled process-group RSS is not a kernel-enforced memory cap.",
        "memory_monitoring": {
          "budget_bytes": 32000000000,
          "enforcement": "sampled_process_group_rss",
          "exceeded": false,
          "kernel_memory_limit_enforced": false,
          "notes": "RSS sampling can miss brief peaks and counts shared pages in each process. It excludes GPU VRAM and does not reserve RAM or constrain other instance work.",
          "sampled_process_group_peak_rss_bytes": 7440216064,
          "samples": 324
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
          "differometor/simulate.py": "821227035235395214cdd4bd7f793b99958d08d05709ac3dbd8ba2841abc83b6",
          "differometor/utils.py": "73ee8a862cbc435363904addc363071ed7dc8b1546956f82e1746998fe3b09ff"
        },
        "worker_sha256": "d3c212da0ab1215187407d9cd21dc2cbb5f88dc0b5ee7885135bf7f002d14b58"
      },
      "validated_output_scope": "last_warm_evaluation",
      "warm_metrics": {
        "forward": 8.69833411462605,
        "gradient": 1.4250375777482986,
        "host_transfer": 0.00022575818002223969,
        "sensitivity": 0.10757383704185486
      },
      "worker_error": null
    }
  ],
  "evidence_ids": [
    "955f9c9b082c4cb8a74af964baa7290c:46c75f8de93ce199d794f52f5ab3de4c5af0de4bc6ecef00ca8993aae2dc85f7",
    "48775628352f423f9d4dbe90af6b54e8:32e35e2148292f98536c412ddcb655a7d61881911219c76647d34b4ffb24ca29"
  ],
  "git_parents": null,
  "heuristic_id": null,
  "hypothesis": null,
  "improved": false,
  "kind": "mutate",
  "lane_id": "tune",
  "metrics": {
    "compilation": 10.998526081442833,
    "forward": 8.333781151100993,
    "gradient": 1.432364558801055,
    "peak_rss_bytes": 7439167488,
    "runtime": 9.767398297786713,
    "sensitivity": 0.0009126197546720505,
    "setup": 1.1018755566328764,
    "total": 21.867799935862422,
    "transfer": 0.00033996812999248505
  },
  "model_manifest": null,
  "owner": "coordinator",
  "owner_version": 1,
  "parameters": {
    "factor_mode": "direct",
    "noise_mode": "broadcast"
  },
  "parameters_after": {
    "factor_mode": "direct",
    "noise_mode": "broadcast"
  },
  "parameters_before": null,
  "parents": [
    "topology-seed"
  ],
  "prompt_sha256": null,
  "proposal": {
    "candidate_id": "7a6936e264024fc7a629cbc5e75ec8d3",
    "commit_sha": "8427aae28bd8bb2b248e833fa416ce0563d53c9e",
    "content_sha256": "151c29a4b285ee3987696bf8adc9dd02f1dc7a0fe518a59d1f5bbbc0298103d7",
    "kind": "mutate",
    "lane_id": "tune",
    "parameters": {
      "factor_mode": "direct",
      "noise_mode": "broadcast"
    },
    "parents": [
      "topology-seed"
    ],
    "proposal_id": "7a6936e264024fc7a629cbc5e75ec8d3",
    "provenance": {
      "context": {
        "bytes": 1224,
        "path": "contexts/1ff9aec642628f0a7d868704d857c106fc3ec6fe91799c4b5c34b2400e115182.json",
        "sha256": "1ff9aec642628f0a7d868704d857c106fc3ec6fe91799c4b5c34b2400e115182"
      },
      "context_sha256": "b3c7e7a58f29d670bdf0366671395a448112d7fa35418084fd6ff581fd9c8a0a",
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
  "proposal_id": "7a6936e264024fc7a629cbc5e75ec8d3",
  "provenance": {
    "context": {
      "bytes": 1224,
      "path": "contexts/1ff9aec642628f0a7d868704d857c106fc3ec6fe91799c4b5c34b2400e115182.json",
      "sha256": "1ff9aec642628f0a7d868704d857c106fc3ec6fe91799c4b5c34b2400e115182"
    },
    "context_sha256": "b3c7e7a58f29d670bdf0366671395a448112d7fa35418084fd6ff581fd9c8a0a",
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

### f28325fb234141beb0f0054e7161f709

```json
{
  "cohort_digest": "10567ad0f8dcb7122b6b182e1be342313b89eef340d4070073fdf62d6342204c",
  "commit_sha": "3a2073ad5add8770eab0d37b55ad67cea71b448b",
  "content_sha256": "42c391a50cf00af605afe0a0d2e7b5ac348829ace3e40ed406a8055b1c587142",
  "context_sha256": null,
  "evaluation_requests": [
    {
      "attempt": 1,
      "candidate_id": "f28325fb234141beb0f0054e7161f709",
      "evidence_id": "004ac1572615488caf91628b849da147:e23d4ea50664b359224f93998019b986ccb3065f06f7e7179f7244a929e263bc",
      "imported": false,
      "job_id": "004ac1572615488caf91628b849da147",
      "profile": "screen",
      "request_id": "31ff7d4491094561ab57c0865d0a3776",
      "status": "screen"
    },
    {
      "attempt": 1,
      "candidate_id": "f28325fb234141beb0f0054e7161f709",
      "evidence_id": "d9a90c7ee1974e64a4aebcef47572111:38345588a583bc5d8e10c81e4a51b2a962c05ec4147010931203b6e8b7f3a836",
      "imported": false,
      "job_id": "d9a90c7ee1974e64a4aebcef47572111",
      "profile": "full",
      "request_id": "b0d84fd36765435cb9c4de4043298e28",
      "status": "valid"
    }
  ],
  "evidence": [
    {
      "artifact_digest": "e23d4ea50664b359224f93998019b986ccb3065f06f7e7179f7244a929e263bc",
      "artifact_digests": {
        "report.json": "a81910c8e5b51fc0d81de508fe349340c6021ff26a8fc33df4660109f737f03d",
        "result": "c51598ec48797b8f716bf9c71adb04676f6555b1ed39c1e9cc85bd3e9ae9ed44"
      },
      "candidate_sha": "3a2073ad5add8770eab0d37b55ad67cea71b448b",
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
          "budget_bytes": 32000000000,
          "enforcement": "sampled_process_group_rss",
          "kernel_memory_limit_enforced": false
        },
        "profile": "screen",
        "protected_baseline_sha": "02ec741d8a1bf1a2278294ea74f9fc1d68f08f1f",
        "signature": {
          "environment": {
            "backend": "cpu",
            "cpu_affinity_ids": [
              2
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
      "cohort_digest": "fc9228f32197f0d2653ba0de06fc01d528953444ab2039dbff6e1284cf689351",
      "cost": {
        "peak_rss_bytes": 6506156032,
        "peak_rss_kib": 6353668,
        "total_worker_wall_seconds": 22.139999218285084,
        "wall_seconds": 22.139999218285084
      },
      "eligible_full": false,
      "evidence_digest": "2c6f2e2c5231057204100252fd57485d61ec0b3b3dece0daecc509e61edba706",
      "evidence_id": "004ac1572615488caf91628b849da147:e23d4ea50664b359224f93998019b986ccb3065f06f7e7179f7244a929e263bc",
      "execution_status": "completed",
      "issues": [],
      "job_id": "004ac1572615488caf91628b849da147",
      "metrics": {
        "compilation": 10.990279512479901,
        "forward": 7.906666144728661,
        "gradient": 1.227997524663806,
        "peak_rss_bytes": 6506156032,
        "runtime": 9.135899676010013,
        "sensitivity": 0.000903841108083725,
        "setup": 1.1165588982403278,
        "total": 21.24273808673024,
        "transfer": 0.00033216550946235657
      },
      "phases": {
        "build": 0.8123206496238708,
        "forward": 7.906666144728661,
        "forward_compile": 7.68315788730979,
        "forward_lower": 0.8200774360448122,
        "gradient": 1.227997524663806,
        "gradient_compile": 1.933327343314886,
        "gradient_lower": 0.1826826874166727,
        "host_transfer": 0.00033216550946235657,
        "imports": 0.2998523451387882,
        "initialize": 0.002898169681429863,
        "load": 0.0014877337962388992,
        "sensitivity": 0.000903841108083725,
        "sensitivity_compile": 0.2808862291276455,
        "sensitivity_lower": 0.09014792926609516
      },
      "profile": "screen",
      "resource_evidence": {
        "budget_bytes": 32000000000,
        "container_limits": {
          "cpu.max": "1600000 100000",
          "cpuset.cpus.effective": "0-127",
          "memory.max": "59055800320",
          "memory.swap.max": "0"
        },
        "limitation": "Sampled process-group RSS is not a kernel-enforced memory cap.",
        "memory_monitoring": {
          "budget_bytes": 32000000000,
          "enforcement": "sampled_process_group_rss",
          "exceeded": false,
          "kernel_memory_limit_enforced": false,
          "notes": "RSS sampling can miss brief peaks and counts shared pages in each process. It excludes GPU VRAM and does not reserve RAM or constrain other instance work.",
          "sampled_process_group_peak_rss_bytes": 6506156032,
          "samples": 84
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
          "differometor/simulate.py": "d71429521fe64e53ac5d54e4a29483f184d52b2d04ae6a8d5c13b75012d2cf89",
          "differometor/utils.py": "73ee8a862cbc435363904addc363071ed7dc8b1546956f82e1746998fe3b09ff"
        },
        "worker_sha256": "d3c212da0ab1215187407d9cd21dc2cbb5f88dc0b5ee7885135bf7f002d14b58"
      },
      "validated_output_scope": "first_evaluation",
      "warm_metrics": {},
      "worker_error": null
    },
    {
      "artifact_digest": "38345588a583bc5d8e10c81e4a51b2a962c05ec4147010931203b6e8b7f3a836",
      "artifact_digests": {
        "comparison.json": "8d853e7258e46f45a450e859401bf26efeedf5eb76c10eeff97b193bbffd93ae",
        "report.json": "f4529ff79c16293ddde3c5ca9647e650320a0fb44bf07498206bd0df66880057",
        "result": "a2714e1b6b56083bfdf4da927f5b340628ceb1a177c617ba19853a4257194526"
      },
      "candidate_sha": "3a2073ad5add8770eab0d37b55ad67cea71b448b",
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
          "budget_bytes": 32000000000,
          "enforcement": "sampled_process_group_rss",
          "kernel_memory_limit_enforced": false
        },
        "profile": "full",
        "protected_baseline_sha": "02ec741d8a1bf1a2278294ea74f9fc1d68f08f1f",
        "signature": {
          "environment": {
            "backend": "cpu",
            "cpu_affinity_ids": [
              2
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
      "cohort_digest": "10567ad0f8dcb7122b6b182e1be342313b89eef340d4070073fdf62d6342204c",
      "cost": {
        "comparison_wall_seconds": 0.26475697197020054,
        "peak_rss_bytes": 6501539840,
        "peak_rss_kib": 6349160,
        "total_worker_wall_seconds": 80.91775886900723,
        "wall_seconds": 80.65300189703703
      },
      "eligible_full": true,
      "evidence_digest": "3ea5f8dc9784481e279d483db59abbb0eef5360763016fbc61d52f01ab6f9be5",
      "evidence_id": "d9a90c7ee1974e64a4aebcef47572111:38345588a583bc5d8e10c81e4a51b2a962c05ec4147010931203b6e8b7f3a836",
      "execution_status": "completed",
      "issues": [],
      "job_id": "d9a90c7ee1974e64a4aebcef47572111",
      "metrics": {
        "compilation": 10.947299595922232,
        "forward": 7.905136497691274,
        "gradient": 1.2312706671655178,
        "peak_rss_bytes": 6501539840,
        "runtime": 9.137616651132703,
        "sensitivity": 0.0008617900311946869,
        "setup": 1.1149214282631874,
        "total": 21.199837675318122,
        "transfer": 0.0003476962447166443
      },
      "phases": {
        "build": 0.815430199727416,
        "forward": 7.905136497691274,
        "forward_compile": 7.60852031968534,
        "forward_lower": 0.8265079949051142,
        "gradient": 1.2312706671655178,
        "gradient_compile": 1.9528383687138557,
        "gradient_lower": 0.18384249694645405,
        "host_transfer": 0.0003476962447166443,
        "imports": 0.2950796838849783,
        "initialize": 0.002918500453233719,
        "load": 0.0014930441975593567,
        "sensitivity": 0.0008617900311946869,
        "sensitivity_compile": 0.2856659572571516,
        "sensitivity_lower": 0.08992445841431618
      },
      "profile": "full",
      "resource_evidence": {
        "budget_bytes": 32000000000,
        "container_limits": {
          "cpu.max": "1600000 100000",
          "cpuset.cpus.effective": "0-127",
          "memory.max": "59055800320",
          "memory.swap.max": "0"
        },
        "limitation": "Sampled process-group RSS is not a kernel-enforced memory cap.",
        "memory_monitoring": {
          "budget_bytes": 32000000000,
          "enforcement": "sampled_process_group_rss",
          "exceeded": false,
          "kernel_memory_limit_enforced": false,
          "notes": "RSS sampling can miss brief peaks and counts shared pages in each process. It excludes GPU VRAM and does not reserve RAM or constrain other instance work.",
          "sampled_process_group_peak_rss_bytes": 6502588416,
          "samples": 307
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
          "differometor/simulate.py": "d71429521fe64e53ac5d54e4a29483f184d52b2d04ae6a8d5c13b75012d2cf89",
          "differometor/utils.py": "73ee8a862cbc435363904addc363071ed7dc8b1546956f82e1746998fe3b09ff"
        },
        "worker_sha256": "d3c212da0ab1215187407d9cd21dc2cbb5f88dc0b5ee7885135bf7f002d14b58"
      },
      "validated_output_scope": "last_warm_evaluation",
      "warm_metrics": {
        "forward": 7.909765858203173,
        "gradient": 1.2420729994773865,
        "host_transfer": 0.0002254582941532135,
        "sensitivity": 0.11706080660223961
      },
      "worker_error": null
    }
  ],
  "evidence_ids": [
    "004ac1572615488caf91628b849da147:e23d4ea50664b359224f93998019b986ccb3065f06f7e7179f7244a929e263bc",
    "d9a90c7ee1974e64a4aebcef47572111:38345588a583bc5d8e10c81e4a51b2a962c05ec4147010931203b6e8b7f3a836"
  ],
  "git_parents": null,
  "heuristic_id": null,
  "hypothesis": null,
  "improved": true,
  "kind": "mutate",
  "lane_id": "tune",
  "metrics": {
    "compilation": 10.947299595922232,
    "forward": 7.905136497691274,
    "gradient": 1.2312706671655178,
    "peak_rss_bytes": 6501539840,
    "runtime": 9.137616651132703,
    "sensitivity": 0.0008617900311946869,
    "setup": 1.1149214282631874,
    "total": 21.199837675318122,
    "transfer": 0.0003476962447166443
  },
  "model_manifest": null,
  "owner": "coordinator",
  "owner_version": 1,
  "parameters": {
    "factor_mode": "direct",
    "noise_mode": "shared"
  },
  "parameters_after": {
    "factor_mode": "direct",
    "noise_mode": "shared"
  },
  "parameters_before": null,
  "parents": [
    "7a6936e264024fc7a629cbc5e75ec8d3"
  ],
  "prompt_sha256": null,
  "proposal": {
    "candidate_id": "f28325fb234141beb0f0054e7161f709",
    "commit_sha": "3a2073ad5add8770eab0d37b55ad67cea71b448b",
    "content_sha256": "42c391a50cf00af605afe0a0d2e7b5ac348829ace3e40ed406a8055b1c587142",
    "kind": "mutate",
    "lane_id": "tune",
    "parameters": {
      "factor_mode": "direct",
      "noise_mode": "shared"
    },
    "parents": [
      "7a6936e264024fc7a629cbc5e75ec8d3"
    ],
    "proposal_id": "f28325fb234141beb0f0054e7161f709",
    "provenance": {
      "context": {
        "bytes": 1518,
        "path": "contexts/22d823e2ad17876eff18847fb62532ae16c777587eb8c5ca6c6e82ea8784551b.json",
        "sha256": "22d823e2ad17876eff18847fb62532ae16c777587eb8c5ca6c6e82ea8784551b"
      },
      "context_sha256": "0b58962ea3ecf89d5a56e71764185d05b874bfc586e5259adcd36f4ddae3f8da",
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
  "proposal_id": "f28325fb234141beb0f0054e7161f709",
  "provenance": {
    "context": {
      "bytes": 1518,
      "path": "contexts/22d823e2ad17876eff18847fb62532ae16c777587eb8c5ca6c6e82ea8784551b.json",
      "sha256": "22d823e2ad17876eff18847fb62532ae16c777587eb8c5ca6c6e82ea8784551b"
    },
    "context_sha256": "0b58962ea3ecf89d5a56e71764185d05b874bfc586e5259adcd36f4ddae3f8da",
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

## Decision and failure trail

| Sequence | Event | Actor | Detail |
| --- | --- | --- | --- |
| 1 | campaign_initialized | coordinator | {"spec_digest": "7120f76767786f83b48bfe836708a978efb09e140b2fc4e29fd70334b159ebae"} |
| 2 | owner_claimed | coordinator | {"actor": "coordinator", "role": "coordinator", "version": 1} |
| 3 | round_created | coordinator | {"round_id": "topology-001", "spec_digest": "a998fa82854524d2d6272100fdc7817495162e4b5af51b45dd113f04b3d46d1d", "version": 1} |
| 4 | candidate_proposed | coordinator | {"candidate_id": "topology-seed", "duplicate_of": null, "owner_version": 1, "proposal_digest": "51f9880c04d3c6266f955f6ac92e96f0ed4a6b6e4d24a97e3c5a0882be3fff81", "proposal_id": "topology-seed"} |
| 5 | evidence_observed | coordinator | {"candidate_id": "topology-seed", "category": "valid", "evidence_digest": "43f152c466fc67eb9999c285842b6454d973cb2853d96a824f02d1a93243030b", "evidence_id": "d07456c28e8647289ddf32fd9676bf0d:acb6f2e3adb36a5a0d76489a61f11270265d6e92d3833b7e9241808a32cbd21d", "job_id": "d07456c28e8647289ddf32fd9676bf0d", "progress": null, "status": "valid", "strikes": 0} |
| 6 | decision_recorded | coordinator | {"decision_id": "7a6936e264024fc7a629cbc5e75ec8d3", "payload": {"context": {"bytes": 1224, "path": "contexts/1ff9aec642628f0a7d868704d857c106fc3ec6fe91799c4b5c34b2400e115182.json", "sha256": "1ff9aec642628f0a7d868704d857c106fc3ec6fe91799c4b5c34b2400e115182"}, "model_trained": false, "origin": "local-startup", "selection_origin": "local-startup", "training_configurations": 1}, "payload_digest": "00209e09a2ead800346ebf9640579d57f0db4f07596c0a1cd3057b89f69df131"} |
| 7 | candidate_proposed | coordinator | {"candidate_id": "7a6936e264024fc7a629cbc5e75ec8d3", "duplicate_of": null, "owner_version": 1, "proposal_digest": "45fa9732d1422e40e79a7dc99125b846d253816007b88c2f607e9aaf387cd982", "proposal_id": "7a6936e264024fc7a629cbc5e75ec8d3"} |
| 8 | evaluation_reserved | coordinator | {"attempt": 1, "candidate_id": "7a6936e264024fc7a629cbc5e75ec8d3", "profile": "screen", "request_id": "2c5df883c5fe485389887f918de84941"} |
| 9 | evaluation_bound | coordinator | {"job_id": "955f9c9b082c4cb8a74af964baa7290c", "request_id": "2c5df883c5fe485389887f918de84941"} |
| 10 | evidence_observed | coordinator | {"candidate_id": "7a6936e264024fc7a629cbc5e75ec8d3", "category": "screen", "evidence_digest": "ebc4e3f8a973dbb4a4999c121009f85ad72b135bb9d8d15432b6696413f6971e", "evidence_id": "955f9c9b082c4cb8a74af964baa7290c:46c75f8de93ce199d794f52f5ab3de4c5af0de4bc6ecef00ca8993aae2dc85f7", "job_id": "955f9c9b082c4cb8a74af964baa7290c", "progress": null, "status": "screened", "strikes": 0} |
| 11 | evaluation_reserved | coordinator | {"attempt": 1, "candidate_id": "7a6936e264024fc7a629cbc5e75ec8d3", "profile": "full", "request_id": "7018c7f78f9d4aa1b86189afcbe615c5"} |
| 12 | evaluation_bound | coordinator | {"job_id": "48775628352f423f9d4dbe90af6b54e8", "request_id": "7018c7f78f9d4aa1b86189afcbe615c5"} |
| 13 | evidence_observed | coordinator | {"candidate_id": "7a6936e264024fc7a629cbc5e75ec8d3", "category": "valid", "evidence_digest": "a098f83d5e45f542888150b932712c6af8a82e39c6ffa3bce6bc05114ec074f8", "evidence_id": "48775628352f423f9d4dbe90af6b54e8:32e35e2148292f98536c412ddcb655a7d61881911219c76647d34b4ffb24ca29", "job_id": "48775628352f423f9d4dbe90af6b54e8", "progress": {"axes": ["setup", "compilation", "forward", "sensitivity", "gradient", "transfer"], "meaningful_pareto": false, "meaningful_total": false, "policy": {"absolute": 0.02, "relative": 0.01}, "reference_best_total": 21.98474472016096, "reference_parents": ["topology-seed"]}, "status": "valid", "strikes": 1} |
| 14 | decision_recorded | coordinator | {"decision_id": "f28325fb234141beb0f0054e7161f709", "payload": {"context": {"bytes": 1518, "path": "contexts/22d823e2ad17876eff18847fb62532ae16c777587eb8c5ca6c6e82ea8784551b.json", "sha256": "22d823e2ad17876eff18847fb62532ae16c777587eb8c5ca6c6e82ea8784551b"}, "model_trained": false, "origin": "local-startup", "selection_origin": "local-startup", "training_configurations": 2}, "payload_digest": "d70ff919e4aaa10bda166d354c8d8c74baf4481a9e17bb8dce0fb1f85536d69b"} |
| 15 | candidate_proposed | coordinator | {"candidate_id": "f28325fb234141beb0f0054e7161f709", "duplicate_of": null, "owner_version": 1, "proposal_digest": "d8f5b337606730e48d6b9996a00bb6300829bbfb959b95374b4f1b6b10a4da69", "proposal_id": "f28325fb234141beb0f0054e7161f709"} |
| 16 | evaluation_reserved | coordinator | {"attempt": 1, "candidate_id": "f28325fb234141beb0f0054e7161f709", "profile": "screen", "request_id": "31ff7d4491094561ab57c0865d0a3776"} |
| 17 | evaluation_bound | coordinator | {"job_id": "004ac1572615488caf91628b849da147", "request_id": "31ff7d4491094561ab57c0865d0a3776"} |
| 18 | evidence_observed | coordinator | {"candidate_id": "f28325fb234141beb0f0054e7161f709", "category": "screen", "evidence_digest": "982c5147ffe7e1075af45b9335c63638d8d3f3930dbfa19cb2586501c027e7be", "evidence_id": "004ac1572615488caf91628b849da147:e23d4ea50664b359224f93998019b986ccb3065f06f7e7179f7244a929e263bc", "job_id": "004ac1572615488caf91628b849da147", "progress": null, "status": "screened", "strikes": 1} |
| 19 | evaluation_reserved | coordinator | {"attempt": 1, "candidate_id": "f28325fb234141beb0f0054e7161f709", "profile": "full", "request_id": "b0d84fd36765435cb9c4de4043298e28"} |
| 20 | evaluation_bound | coordinator | {"job_id": "d9a90c7ee1974e64a4aebcef47572111", "request_id": "b0d84fd36765435cb9c4de4043298e28"} |
| 21 | evidence_observed | coordinator | {"candidate_id": "f28325fb234141beb0f0054e7161f709", "category": "valid", "evidence_digest": "4c01e2f1d33d4f3f8f495a0a835df73708a858bbea706eef90dd0c84550e7405", "evidence_id": "d9a90c7ee1974e64a4aebcef47572111:38345588a583bc5d8e10c81e4a51b2a962c05ec4147010931203b6e8b7f3a836", "job_id": "d9a90c7ee1974e64a4aebcef47572111", "progress": {"axes": ["setup", "compilation", "forward", "sensitivity", "gradient", "transfer"], "meaningful_pareto": true, "meaningful_total": true, "policy": {"absolute": 0.02, "relative": 0.01}, "reference_best_total": 21.867799935862422, "reference_parents": ["7a6936e264024fc7a629cbc5e75ec8d3"]}, "status": "valid", "strikes": 0} |
| 22 | decision_recorded | coordinator | {"decision_id": "399d435fe5dc428ab5af928cdfed7757", "payload": {"context": {"bytes": 1809, "path": "contexts/9b961a44bce14439c2d32301a647e53aef93757ad82a40c5986c8c87464a11c0.json", "sha256": "9b961a44bce14439c2d32301a647e53aef93757ad82a40c5986c8c87464a11c0"}, "model_trained": false, "origin": "local-startup", "selection_origin": "local-startup", "training_configurations": 3}, "payload_digest": "86234ddfeb652d1f846bb1d60fdc807b6c375a5140ea8596855ea8f0fbd1c475"} |

Guidance may propose a new round. It cannot silently replace frozen operators, ownership, evaluation requirements or budgets. Only the coordinator can admit that round through the campaign state API. Publishing this ledger does not merge or promote candidate code.
