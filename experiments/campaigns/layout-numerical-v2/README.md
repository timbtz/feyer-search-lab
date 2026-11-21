# Campaign layout-numerical-v2

Export schema: `feyer-campaign-export-v1`. Snapshot: `8cdde136da129577196646d501a3a876b210ddbc80d6acc3c576ff832b39c94a`.

[Frozen proposer context](contexts/8b0f092838e080160ae656119d6791fc020879327bd2ff47ae9be81b3162db32.json) — SHA256 `8b0f092838e080160ae656119d6791fc020879327bd2ff47ae9be81b3162db32`.

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
  n1["7a6936e264024fc7a629cbc5e75ec8d3 mutate proposed"]
  n0 -->|mutate| n1
```

## Candidate outcomes

| Candidate | Round / lane | Scientific parents | Exact commit | State | First-run seconds | Evidence IDs |
| --- | --- | --- | --- | --- | --- | --- |
| topology-seed | topology-001 / tune | root | e0a1dc69f4951c100fefbc9fc08a23c3c12058dc | valid | 21.9847 | d07456c28e8647289ddf32fd9676bf0d:acb6f2e3adb36a5a0d76489a61f11270265d6e92d3833b7e9241808a32cbd21d |
| 7a6936e264024fc7a629cbc5e75ec8d3 | topology-001 / tune | topology-seed | 8427aae28bd8bb2b248e833fa416ce0563d53c9e | proposed | unknown | none |

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

- topology-001/tune: active; owner coordinator; strikes 0; reason not recorded

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
  "cohort_digest": null,
  "commit_sha": "8427aae28bd8bb2b248e833fa416ce0563d53c9e",
  "content_sha256": "151c29a4b285ee3987696bf8adc9dd02f1dc7a0fe518a59d1f5bbbc0298103d7",
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
  "valid": false
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

Guidance may propose a new round. It cannot silently replace frozen operators, ownership, evaluation requirements or budgets. Only the coordinator can admit that round through the campaign state API. Publishing this ledger does not merge or promote candidate code.
