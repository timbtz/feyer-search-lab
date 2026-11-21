# Campaign topology-smac-v1

Export schema: `feyer-campaign-export-v1`. Snapshot: `ef63d781aa208e914b09ccd054ab6a9c181b397b124b939f0ada90ea76c4c4ca`.

[Frozen proposer context](contexts/52f3fc17bd948574280f55fef603623fd502e54ef536a4c1611da2b46337837c.json) — SHA256 `52f3fc17bd948574280f55fef603623fd502e54ef536a4c1611da2b46337837c`.

This is an evidence ledger. Scientific parents describe chosen inputs to an experiment; they are not necessarily Git parents. Phase changes are observations, not proof that one edit caused the difference. A failed attempt remains part of the history.

## Ownership and frozen policy

Campaign specification digest: `2bb349e1e62aecd25f8534e759dd3bbe1b50083c1e32d6cd7cdbdb61c05c4810`.

| Actor | Role | Ownership version | Active |
| --- | --- | --- | --- |
| coordinator | coordinator | 1 | True |

## Scientific lineage

Edges come from declared scientific parents, not inferred chronology or Git ancestry.

```mermaid
graph LR
  n0["topology-seed seed valid"]
  n1["20e51632187a44789960f5eb93948846 mutate valid"]
  n0 -->|mutate| n1
```

## Candidate outcomes

| Candidate | Round / lane | Scientific parents | Exact commit | State | First-run seconds | Evidence IDs |
| --- | --- | --- | --- | --- | --- | --- |
| topology-seed | topology-001 / tune | root | f3139c71ae2a5c9de2b015aad7db1a730fac0e1e | valid | 23.3201 | 5089ae06eb04473a87bc1207cb411d8c:c69386d737dffa9b68812bfa3d686126fb0e0d1415977412443757a6603a6439 |
| 20e51632187a44789960f5eb93948846 | topology-001 / tune | topology-seed | b2d63e018faaae32429af9ea7f3663c8dec53635 | valid | 23.8838 | 9e49c2fdf851489d8d0b5d855e10cd53:5dc633a525eeb1fed116343e0a1b6593cdc3465849842dea7617c5b277213592, 160efd6760d941e998dd5026d63de511:b276711c5529630ed85c3a3d9e9f22a678d105db2296fe41aedf88821ab86481 |

## Round decisions and stalled work

### Round topology-001

Frozen specification: `2efeba46fb51ad4ae20f324f85279da6764e86dc57f87673f8d83e8a7602dbc1`; version: 1; closed: False.

```json
{
  "budget": {
    "deadline_unix": 1795288990.0,
    "max_evaluations": 10,
    "max_model_calls": 0,
    "max_proposals": 9
  },
  "dimensions": {
    "frequency_chunk": [
      1,
      2,
      4,
      8
    ],
    "noise_reuse": [
      true,
      false
    ]
  },
  "lanes": {
    "tune": {
      "dimensions": [
        "noise_reuse",
        "frequency_chunk"
      ],
      "max_proposals": 8,
      "owner": "coordinator",
      "stall_limit": 8
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
        "noise_reuse",
        "frequency_chunk"
      ]
    }
  },
  "round_id": "topology-001",
  "seed_parameters": {
    "frequency_chunk": 1,
    "noise_reuse": true
  }
}
```

- topology-001/tune: ready; owner coordinator; strikes 1; reason not recorded

## Candidate evidence and proposed changes

### topology-seed

```json
{
  "cohort_digest": "10567ad0f8dcb7122b6b182e1be342313b89eef340d4070073fdf62d6342204c",
  "commit_sha": "f3139c71ae2a5c9de2b015aad7db1a730fac0e1e",
  "content_sha256": "7fec013c04c9daa7d25633d12743acbc5f6f2b4fc7e3d21d465c15d9af16ff62",
  "context_sha256": null,
  "evaluation_requests": [
    {
      "attempt": 1,
      "candidate_id": "topology-seed",
      "evidence_id": "5089ae06eb04473a87bc1207cb411d8c:c69386d737dffa9b68812bfa3d686126fb0e0d1415977412443757a6603a6439",
      "imported": true,
      "job_id": "5089ae06eb04473a87bc1207cb411d8c",
      "profile": "full",
      "request_id": "b735da4386044e61826b3a8a0a2c4e9d",
      "status": "valid"
    }
  ],
  "evidence": [
    {
      "artifact_digest": "c69386d737dffa9b68812bfa3d686126fb0e0d1415977412443757a6603a6439",
      "artifact_digests": {
        "comparison.json": "53db6296074a20f8e3e7d78deadfb85143c844ea4844432e77356e1aabd3110c",
        "report.json": "4ba70c4bb37c332d60ed97cd692a2c797ea853e2272750cbf6ab898b15a3284d",
        "result": "de2facc511bbc27d35987eddb7999eda7649b398735fe714f970bb3caed20fa5"
      },
      "candidate_sha": "f3139c71ae2a5c9de2b015aad7db1a730fac0e1e",
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
        "comparison_wall_seconds": 0.2624017111957073,
        "peak_rss_bytes": 10169511936,
        "peak_rss_kib": 9931164,
        "total_worker_wall_seconds": 93.20249903015792,
        "wall_seconds": 92.94009731896222
      },
      "eligible_full": true,
      "evidence_digest": "0eb15049d36951e9dc029ebdb4924c5487965045fd1427435838fa42a1ba2e58",
      "evidence_id": "5089ae06eb04473a87bc1207cb411d8c:c69386d737dffa9b68812bfa3d686126fb0e0d1415977412443757a6603a6439",
      "execution_status": "completed",
      "issues": [],
      "job_id": "5089ae06eb04473a87bc1207cb411d8c",
      "metrics": {
        "compilation": 11.064241604879498,
        "forward": 9.220779228955507,
        "gradient": 1.9115544147789478,
        "peak_rss_bytes": 10169511936,
        "runtime": 11.133533842861652,
        "sensitivity": 0.0008762199431657791,
        "setup": 1.1223442014306784,
        "total": 23.32011964917183,
        "transfer": 0.0003239791840314865
      },
      "phases": {
        "build": 0.820046192035079,
        "forward": 9.220779228955507,
        "forward_compile": 7.679657740518451,
        "forward_lower": 0.8124177809804678,
        "gradient": 1.9115544147789478,
        "gradient_compile": 1.9631247501820326,
        "gradient_lower": 0.17493822425603867,
        "host_transfer": 0.0003239791840314865,
        "imports": 0.297987112775445,
        "initialize": 0.0029040593653917313,
        "load": 0.0014068372547626495,
        "sensitivity": 0.0008762199431657791,
        "sensitivity_compile": 0.3437984026968479,
        "sensitivity_lower": 0.09030470624566078
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
          "sampled_process_group_peak_rss_bytes": 10170560512,
          "samples": 357
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
          "differometor/simulate.py": "9671189dcc2b4885950e426c4f2d3f8aa7373fb026ccfeef4ca1d54739a5e64f",
          "differometor/utils.py": "73ee8a862cbc435363904addc363071ed7dc8b1546956f82e1746998fe3b09ff"
        },
        "worker_sha256": "d3c212da0ab1215187407d9cd21dc2cbb5f88dc0b5ee7885135bf7f002d14b58"
      },
      "validated_output_scope": "last_warm_evaluation",
      "warm_metrics": {
        "forward": 9.809957098215818,
        "gradient": 1.8867328967899084,
        "host_transfer": 0.00022433698177337646,
        "sensitivity": 0.17540879175066948
      },
      "worker_error": null
    }
  ],
  "evidence_ids": [
    "5089ae06eb04473a87bc1207cb411d8c:c69386d737dffa9b68812bfa3d686126fb0e0d1415977412443757a6603a6439"
  ],
  "git_parents": null,
  "heuristic_id": null,
  "hypothesis": null,
  "improved": false,
  "kind": "seed",
  "lane_id": "tune",
  "metrics": {
    "compilation": 11.064241604879498,
    "forward": 9.220779228955507,
    "gradient": 1.9115544147789478,
    "peak_rss_bytes": 10169511936,
    "runtime": 11.133533842861652,
    "sensitivity": 0.0008762199431657791,
    "setup": 1.1223442014306784,
    "total": 23.32011964917183,
    "transfer": 0.0003239791840314865
  },
  "model_manifest": null,
  "owner": "coordinator",
  "owner_version": 1,
  "parameters": {
    "frequency_chunk": 1,
    "noise_reuse": true
  },
  "parameters_after": {
    "frequency_chunk": 1,
    "noise_reuse": true
  },
  "parameters_before": null,
  "parents": [],
  "prompt_sha256": null,
  "proposal": {
    "candidate_id": "topology-seed",
    "commit_sha": "f3139c71ae2a5c9de2b015aad7db1a730fac0e1e",
    "content_sha256": "7fec013c04c9daa7d25633d12743acbc5f6f2b4fc7e3d21d465c15d9af16ff62",
    "kind": "seed",
    "lane_id": "tune",
    "parameters": {
      "frequency_chunk": 1,
      "noise_reuse": true
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

### 20e51632187a44789960f5eb93948846

```json
{
  "cohort_digest": "10567ad0f8dcb7122b6b182e1be342313b89eef340d4070073fdf62d6342204c",
  "commit_sha": "b2d63e018faaae32429af9ea7f3663c8dec53635",
  "content_sha256": "4595bfa80260c597ecc92bd4c907aa1d06ab243887a99463151f42a2ccdb9685",
  "context_sha256": null,
  "evaluation_requests": [
    {
      "attempt": 1,
      "candidate_id": "20e51632187a44789960f5eb93948846",
      "evidence_id": "9e49c2fdf851489d8d0b5d855e10cd53:5dc633a525eeb1fed116343e0a1b6593cdc3465849842dea7617c5b277213592",
      "imported": false,
      "job_id": "9e49c2fdf851489d8d0b5d855e10cd53",
      "profile": "screen",
      "request_id": "c2a9f8ccf0f04aae9f5cae1a5d92ba1b",
      "status": "screen"
    },
    {
      "attempt": 1,
      "candidate_id": "20e51632187a44789960f5eb93948846",
      "evidence_id": "160efd6760d941e998dd5026d63de511:b276711c5529630ed85c3a3d9e9f22a678d105db2296fe41aedf88821ab86481",
      "imported": false,
      "job_id": "160efd6760d941e998dd5026d63de511",
      "profile": "full",
      "request_id": "b933f3a0053d465d8a5c8211c9194cad",
      "status": "valid"
    }
  ],
  "evidence": [
    {
      "artifact_digest": "5dc633a525eeb1fed116343e0a1b6593cdc3465849842dea7617c5b277213592",
      "artifact_digests": {
        "report.json": "148cf40d35d69bebf71dbb9c3a6832f8b8d275afd3b838f346b4148ba395fb46",
        "result": "71fb1345caf31184a0cf75628936355ad57881e16f93bdee472b7d7ceb00f132"
      },
      "candidate_sha": "b2d63e018faaae32429af9ea7f3663c8dec53635",
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
        "peak_rss_bytes": 11047522304,
        "peak_rss_kib": 10788596,
        "total_worker_wall_seconds": 24.733176728710532,
        "wall_seconds": 24.733176728710532
      },
      "eligible_full": false,
      "evidence_digest": "d6717c6fa0d751dd52c7d65be1b7df91c51eca37f532782fea25b37d5d1b8c51",
      "evidence_id": "9e49c2fdf851489d8d0b5d855e10cd53:5dc633a525eeb1fed116343e0a1b6593cdc3465849842dea7617c5b277213592",
      "execution_status": "completed",
      "issues": [],
      "job_id": "9e49c2fdf851489d8d0b5d855e10cd53",
      "metrics": {
        "compilation": 10.9815673828125,
        "forward": 9.3574473336339,
        "gradient": 2.0772590953856707,
        "peak_rss_bytes": 11047522304,
        "runtime": 11.435913003981113,
        "sensitivity": 0.0008866190910339355,
        "setup": 1.110748888924718,
        "total": 23.52822927571833,
        "transfer": 0.00031995587050914764
      },
      "phases": {
        "build": 0.8157667517662048,
        "forward": 9.3574473336339,
        "forward_compile": 7.725278856232762,
        "forward_lower": 0.8093993570655584,
        "gradient": 2.0772590953856707,
        "gradient_compile": 1.8354453518986702,
        "gradient_lower": 0.1751789152622223,
        "host_transfer": 0.00031995587050914764,
        "imports": 0.29055589623749256,
        "initialize": 0.002947285771369934,
        "load": 0.0014789551496505737,
        "sensitivity": 0.0008866190910339355,
        "sensitivity_compile": 0.34368290565907955,
        "sensitivity_lower": 0.09258199669420719
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
          "sampled_process_group_peak_rss_bytes": 11047522304,
          "samples": 95
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
          "differometor/simulate.py": "db79f139de5796dc99ab0bc28eb9bc605fd0af9a10405d2f93f682e851a3bb19",
          "differometor/utils.py": "73ee8a862cbc435363904addc363071ed7dc8b1546956f82e1746998fe3b09ff"
        },
        "worker_sha256": "d3c212da0ab1215187407d9cd21dc2cbb5f88dc0b5ee7885135bf7f002d14b58"
      },
      "validated_output_scope": "first_evaluation",
      "warm_metrics": {},
      "worker_error": null
    },
    {
      "artifact_digest": "b276711c5529630ed85c3a3d9e9f22a678d105db2296fe41aedf88821ab86481",
      "artifact_digests": {
        "comparison.json": "53db6296074a20f8e3e7d78deadfb85143c844ea4844432e77356e1aabd3110c",
        "report.json": "8c65970b915736a218424d0735a9103a688a1b11680afc9be57346800171b306",
        "result": "db72ab6e1e0a0748cb5e77f72caeb215aecae55867d4398322bc0e137502c374"
      },
      "candidate_sha": "b2d63e018faaae32429af9ea7f3663c8dec53635",
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
        "comparison_wall_seconds": 0.2624255530536175,
        "peak_rss_bytes": 11056357376,
        "peak_rss_kib": 10797224,
        "total_worker_wall_seconds": 95.30964922718704,
        "wall_seconds": 95.04722367413342
      },
      "eligible_full": true,
      "evidence_digest": "77254e9558866df188d6915275742b61d86dcc4878dbe583a60646e5352d1489",
      "evidence_id": "160efd6760d941e998dd5026d63de511:b276711c5529630ed85c3a3d9e9f22a678d105db2296fe41aedf88821ab86481",
      "execution_status": "completed",
      "issues": [],
      "job_id": "160efd6760d941e998dd5026d63de511",
      "metrics": {
        "compilation": 11.181336618959904,
        "forward": 9.347755437716842,
        "gradient": 2.2090142481029034,
        "peak_rss_bytes": 11056357376,
        "runtime": 11.558163072913885,
        "sensitivity": 0.0010373406112194061,
        "setup": 1.1442589554935694,
        "total": 23.883758647367358,
        "transfer": 0.00035604648292064667
      },
      "phases": {
        "build": 0.8467485308647156,
        "forward": 9.347755437716842,
        "forward_compile": 7.905797250568867,
        "forward_lower": 0.8223588932305574,
        "gradient": 2.2090142481029034,
        "gradient_compile": 1.840641152113676,
        "gradient_lower": 0.17771470732986927,
        "host_transfer": 0.00035604648292064667,
        "imports": 0.29308460280299187,
        "initialize": 0.002941817045211792,
        "load": 0.0014840047806501389,
        "sensitivity": 0.0010373406112194061,
        "sensitivity_compile": 0.3408184237778187,
        "sensitivity_lower": 0.09400619193911552
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
          "sampled_process_group_peak_rss_bytes": 11057405952,
          "samples": 365
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
          "differometor/simulate.py": "db79f139de5796dc99ab0bc28eb9bc605fd0af9a10405d2f93f682e851a3bb19",
          "differometor/utils.py": "73ee8a862cbc435363904addc363071ed7dc8b1546956f82e1746998fe3b09ff"
        },
        "worker_sha256": "d3c212da0ab1215187407d9cd21dc2cbb5f88dc0b5ee7885135bf7f002d14b58"
      },
      "validated_output_scope": "last_warm_evaluation",
      "warm_metrics": {
        "forward": 10.004870368167758,
        "gradient": 2.0782006308436394,
        "host_transfer": 0.000221937894821167,
        "sensitivity": 0.16793840751051903
      },
      "worker_error": null
    }
  ],
  "evidence_ids": [
    "9e49c2fdf851489d8d0b5d855e10cd53:5dc633a525eeb1fed116343e0a1b6593cdc3465849842dea7617c5b277213592",
    "160efd6760d941e998dd5026d63de511:b276711c5529630ed85c3a3d9e9f22a678d105db2296fe41aedf88821ab86481"
  ],
  "git_parents": null,
  "heuristic_id": null,
  "hypothesis": null,
  "improved": false,
  "kind": "mutate",
  "lane_id": "tune",
  "metrics": {
    "compilation": 11.181336618959904,
    "forward": 9.347755437716842,
    "gradient": 2.2090142481029034,
    "peak_rss_bytes": 11056357376,
    "runtime": 11.558163072913885,
    "sensitivity": 0.0010373406112194061,
    "setup": 1.1442589554935694,
    "total": 23.883758647367358,
    "transfer": 0.00035604648292064667
  },
  "model_manifest": null,
  "owner": "coordinator",
  "owner_version": 1,
  "parameters": {
    "frequency_chunk": 1,
    "noise_reuse": false
  },
  "parameters_after": {
    "frequency_chunk": 1,
    "noise_reuse": false
  },
  "parameters_before": null,
  "parents": [
    "topology-seed"
  ],
  "prompt_sha256": null,
  "proposal": {
    "candidate_id": "20e51632187a44789960f5eb93948846",
    "commit_sha": "b2d63e018faaae32429af9ea7f3663c8dec53635",
    "content_sha256": "4595bfa80260c597ecc92bd4c907aa1d06ab243887a99463151f42a2ccdb9685",
    "kind": "mutate",
    "lane_id": "tune",
    "parameters": {
      "frequency_chunk": 1,
      "noise_reuse": false
    },
    "parents": [
      "topology-seed"
    ],
    "proposal_id": "20e51632187a44789960f5eb93948846",
    "provenance": {
      "context": {
        "bytes": 1342,
        "path": "contexts/375405d3a3f35a9214ef5476da3a4e06c461d6e83b7ac4e7daa14a3b5400bf27.json",
        "sha256": "375405d3a3f35a9214ef5476da3a4e06c461d6e83b7ac4e7daa14a3b5400bf27"
      },
      "context_sha256": "b9dafaa3c81b087c5f078d731920ef931bc083f65c8486b4658f72dec90d1c57",
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
  "proposal_id": "20e51632187a44789960f5eb93948846",
  "provenance": {
    "context": {
      "bytes": 1342,
      "path": "contexts/375405d3a3f35a9214ef5476da3a4e06c461d6e83b7ac4e7daa14a3b5400bf27.json",
      "sha256": "375405d3a3f35a9214ef5476da3a4e06c461d6e83b7ac4e7daa14a3b5400bf27"
    },
    "context_sha256": "b9dafaa3c81b087c5f078d731920ef931bc083f65c8486b4658f72dec90d1c57",
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

## Decision and failure trail

| Sequence | Event | Actor | Detail |
| --- | --- | --- | --- |
| 1 | campaign_initialized | coordinator | {"spec_digest": "2bb349e1e62aecd25f8534e759dd3bbe1b50083c1e32d6cd7cdbdb61c05c4810"} |
| 2 | owner_claimed | coordinator | {"actor": "coordinator", "role": "coordinator", "version": 1} |
| 3 | round_created | coordinator | {"round_id": "topology-001", "spec_digest": "2efeba46fb51ad4ae20f324f85279da6764e86dc57f87673f8d83e8a7602dbc1", "version": 1} |
| 4 | candidate_proposed | coordinator | {"candidate_id": "topology-seed", "duplicate_of": null, "owner_version": 1, "proposal_digest": "c19d9cbe3fafeed9cf090ff5c9527ce0aaeb93a9eba80050d62353b06f2fd4e8", "proposal_id": "topology-seed"} |
| 5 | evidence_observed | coordinator | {"candidate_id": "topology-seed", "category": "valid", "evidence_digest": "21dfe1c6a6a5517a408827a39806f6807626fd1e3142e48c3c7c75994518bde5", "evidence_id": "5089ae06eb04473a87bc1207cb411d8c:c69386d737dffa9b68812bfa3d686126fb0e0d1415977412443757a6603a6439", "job_id": "5089ae06eb04473a87bc1207cb411d8c", "progress": null, "status": "valid", "strikes": 0} |
| 6 | decision_recorded | coordinator | {"decision_id": "20e51632187a44789960f5eb93948846", "payload": {"context": {"bytes": 1342, "path": "contexts/375405d3a3f35a9214ef5476da3a4e06c461d6e83b7ac4e7daa14a3b5400bf27.json", "sha256": "375405d3a3f35a9214ef5476da3a4e06c461d6e83b7ac4e7daa14a3b5400bf27"}, "model_trained": false, "origin": "local-startup", "selection_origin": "local-startup", "training_configurations": 1}, "payload_digest": "5b246337dde4662e96006f6ef6966cfcccfb6887328c0a7cc57e75065aed538f"} |
| 7 | candidate_proposed | coordinator | {"candidate_id": "20e51632187a44789960f5eb93948846", "duplicate_of": null, "owner_version": 1, "proposal_digest": "2461000ca3f36c632ab6340c632bb199d6525cab9e10d77f9bceba9f5c51a19b", "proposal_id": "20e51632187a44789960f5eb93948846"} |
| 8 | evaluation_reserved | coordinator | {"attempt": 1, "candidate_id": "20e51632187a44789960f5eb93948846", "profile": "screen", "request_id": "c2a9f8ccf0f04aae9f5cae1a5d92ba1b"} |
| 9 | evaluation_bound | coordinator | {"job_id": "9e49c2fdf851489d8d0b5d855e10cd53", "request_id": "c2a9f8ccf0f04aae9f5cae1a5d92ba1b"} |
| 10 | evidence_observed | coordinator | {"candidate_id": "20e51632187a44789960f5eb93948846", "category": "screen", "evidence_digest": "e47f80ab561a6b2ad9d21baf6995c2464b13c0264e02a04ac7fb6052809033d2", "evidence_id": "9e49c2fdf851489d8d0b5d855e10cd53:5dc633a525eeb1fed116343e0a1b6593cdc3465849842dea7617c5b277213592", "job_id": "9e49c2fdf851489d8d0b5d855e10cd53", "progress": null, "status": "screened", "strikes": 0} |
| 11 | evaluation_reserved | coordinator | {"attempt": 1, "candidate_id": "20e51632187a44789960f5eb93948846", "profile": "full", "request_id": "b933f3a0053d465d8a5c8211c9194cad"} |
| 12 | evaluation_bound | coordinator | {"job_id": "160efd6760d941e998dd5026d63de511", "request_id": "b933f3a0053d465d8a5c8211c9194cad"} |
| 13 | evidence_observed | coordinator | {"candidate_id": "20e51632187a44789960f5eb93948846", "category": "valid", "evidence_digest": "cdb1a5c8948673a347cd5ac6a8b2ec06f8ae6376611585cc674b7b387740fa5c", "evidence_id": "160efd6760d941e998dd5026d63de511:b276711c5529630ed85c3a3d9e9f22a678d105db2296fe41aedf88821ab86481", "job_id": "160efd6760d941e998dd5026d63de511", "progress": {"axes": ["setup", "compilation", "forward", "sensitivity", "gradient", "transfer"], "meaningful_pareto": false, "meaningful_total": false, "policy": {"absolute": 0.02, "relative": 0.01}, "reference_best_total": 23.32011964917183, "reference_parents": ["topology-seed"]}, "status": "valid", "strikes": 1} |
| 14 | decision_recorded | coordinator | {"decision_id": "17dd8e0384704f5ebc29861318c1262f", "payload": {"context": {"bytes": 1630, "path": "contexts/a1a67fca5cdb43c28a74f3a6d73296fbc3a2e86700a9b8793983c8b092a08d81.json", "sha256": "a1a67fca5cdb43c28a74f3a6d73296fbc3a2e86700a9b8793983c8b092a08d81"}, "model_trained": false, "origin": "local-startup", "selection_origin": "local-startup", "training_configurations": 2}, "payload_digest": "033df6b377c29dff137fb62fde352d5fa176eb2f8c5edd10de9129f551e337f5"} |

Guidance may propose a new round. It cannot silently replace frozen operators, ownership, evaluation requirements or budgets. Only the coordinator can admit that round through the campaign state API. Publishing this ledger does not merge or promote candidate code.
