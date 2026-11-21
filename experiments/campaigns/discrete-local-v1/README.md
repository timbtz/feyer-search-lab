# Campaign discrete-local-v1

Export schema: `feyer-campaign-export-v1`. Snapshot: `dd3a66bf688e7b11b25c1188248de1b813643425683eb43246a069981c72287c`.

[Frozen proposer context](contexts/41e395d5bf7601f71ae755c44233e6179dd15babd97cc99a2aba547c95d6c3f0.json) — SHA256 `41e395d5bf7601f71ae755c44233e6179dd15babd97cc99a2aba547c95d6c3f0`.

This is an evidence ledger. Scientific parents describe chosen inputs to an experiment; they are not necessarily Git parents. Phase changes are observations, not proof that one edit caused the difference. A failed attempt remains part of the history.

## Ownership and frozen policy

Campaign specification digest: `ab43e42f2273d104b7011a29517518470d89f87e9abd9d14ae35df3e3de42b7e`.

| Actor | Role | Ownership version | Active |
| --- | --- | --- | --- |
| coordinator | coordinator | 1 | True |

## Scientific lineage

Edges come from declared scientific parents, not inferred chronology or Git ancestry.

```mermaid
graph LR
  n0["seed8 seed valid"]
  n1["import-42aaabf394d2d9bf5618b6802eb1e11315e85030 seed valid"]
  n2["78273c30837743b594ef628e5c0056f2 mutate valid"]
  n3["1480647fdf514cc7a7a47e78c11dbfbb mutate valid"]
  n0 -->|mutate| n2
  n0 -->|mutate| n3
```

## Candidate outcomes

| Candidate | Round / lane | Scientific parents | Exact commit | State | First-run seconds | Evidence IDs |
| --- | --- | --- | --- | --- | --- | --- |
| seed8 | round-001 / discrete | root | 1e552d675c3795265be8af1ac23ffb61f90f30b1 | valid | 28.0935 | 415bab6b82ef42baa0e0a5277df7aeb9:49937d87a08c533f73470c9dcc48dbc7870c12f467d9a8b5de192dffb5484afa, 882be0c143db470c9686cd2ba9e44c77:b547550f15337f868903dbcb118fa79d025993744270cf25cc8c7816a2e5616d, e6e5badb945c47ae927e511a3ff15fd7:820c7dfc19d0099d62f3b2315da0fb1dd7ee7ee9203b875447cfc2bd07d956a2 |
| import-42aaabf394d2d9bf5618b6802eb1e11315e85030 | round-001 / discrete | root | 42aaabf394d2d9bf5618b6802eb1e11315e85030 | valid | 28.6478 | 7f9a3863201d4908b9e2607e8b925bdc:70e1da46befd5d0fd365188a88a91391f95e2df62042e7a6687de8abbaf8c611 |
| 78273c30837743b594ef628e5c0056f2 | round-001 / discrete | seed8 | 2994693a064e90850c710bd3b3f3317ba525f81b | valid | 36.8441 | 5b3af3628df54f778c117ffaad033a5e:34f77add4e58cd3f92f928160be72ce5d3350ed3868f51fb1e1c1a0fc5e1c9c9, cde035e7126e4e00a4eccc5192f41d86:97a7e880e414101b6593ca85de16889e7fe6e0c28c1e57ad796fb9a0660824be |
| 1480647fdf514cc7a7a47e78c11dbfbb | round-001 / discrete | seed8 | 0955a78b6b96a3aba4bc3eeb1649b211ebf314c1 | valid | 50.1969 | f1c5134330144123bf6a90b7d712a544:663b207a2fd05652d225a8e39268e3768d8906f21c2b46fabb5257540816bac4, 8d433ae433e5496b89cb4de587c0862f:e73ec4d8e0e0b141c91c65a03e7de4e446cb51042c5f42264060bcc887a94bbf |

## Round decisions and stalled work

### Round round-001

Frozen specification: `c9eef3c088d8fc7635ca176417db487b5d2b4472ff28d94dfbae02855d9750d3`; version: 1; closed: False.

```json
{
  "budget": {
    "max_evaluations": 28,
    "max_proposals": 1000
  },
  "constraints": [
    "not checkpoint implies not prevent_cse"
  ],
  "dimensions": {
    "checkpoint": [
      true,
      false
    ],
    "map_batch_size": [
      null,
      1,
      2,
      4,
      8
    ],
    "prevent_cse": [
      false,
      true
    ]
  },
  "lanes": {
    "discrete": {
      "dimensions": [
        "checkpoint",
        "prevent_cse",
        "map_batch_size"
      ],
      "max_proposals": 15,
      "owner": "coordinator",
      "stall_limit": 15
    }
  },
  "materializer_version": "seed8-component-execution-v1",
  "progress": {
    "absolute": 0.02,
    "relative": 0.01
  },
  "recipes": {
    "discrete": {
      "dimensions": [
        "checkpoint",
        "prevent_cse",
        "map_batch_size"
      ]
    }
  },
  "round_id": "round-001",
  "seed_parameters": {
    "checkpoint": true,
    "map_batch_size": null,
    "prevent_cse": false
  },
  "selector": "local-search"
}
```

- round-001/discrete: ready; owner coordinator; strikes 2; reason not recorded

## Candidate evidence and proposed changes

### seed8

```json
{
  "cohort_digest": "10567ad0f8dcb7122b6b182e1be342313b89eef340d4070073fdf62d6342204c",
  "commit_sha": "1e552d675c3795265be8af1ac23ffb61f90f30b1",
  "content_sha256": "8225fedb4580e39fcc3f3611e73e4e356c7c0b55e4a3353486fcad9260d77c01",
  "context_sha256": null,
  "evaluation_requests": [
    {
      "attempt": 1,
      "candidate_id": "seed8",
      "evidence_id": "415bab6b82ef42baa0e0a5277df7aeb9:49937d87a08c533f73470c9dcc48dbc7870c12f467d9a8b5de192dffb5484afa",
      "imported": true,
      "job_id": "415bab6b82ef42baa0e0a5277df7aeb9",
      "profile": "full",
      "request_id": "6ec2f32c284a4aeeb1ed30862a3ee42b",
      "status": "valid"
    },
    {
      "attempt": 2,
      "candidate_id": "seed8",
      "evidence_id": "882be0c143db470c9686cd2ba9e44c77:b547550f15337f868903dbcb118fa79d025993744270cf25cc8c7816a2e5616d",
      "imported": true,
      "job_id": "882be0c143db470c9686cd2ba9e44c77",
      "profile": "full",
      "request_id": "6378fe72ac964ae6bbeb943ce7e6cb91",
      "status": "valid"
    },
    {
      "attempt": 3,
      "candidate_id": "seed8",
      "evidence_id": "e6e5badb945c47ae927e511a3ff15fd7:820c7dfc19d0099d62f3b2315da0fb1dd7ee7ee9203b875447cfc2bd07d956a2",
      "imported": true,
      "job_id": "e6e5badb945c47ae927e511a3ff15fd7",
      "profile": "full",
      "request_id": "d687a2f43e6846fbbb9f30e1449279d1",
      "status": "valid"
    }
  ],
  "evidence": [
    {
      "artifact_digest": "49937d87a08c533f73470c9dcc48dbc7870c12f467d9a8b5de192dffb5484afa",
      "artifact_digests": {
        "comparison.json": "005847678f9babe30a632a5a1a82e2a3edbabb30000bd9d443af41d13038a7d0",
        "report.json": "33b5ce79552d7397bce63da5ef387160c7ef142d72b2acba540c0f610d3a4d2e",
        "result": "7dbb9193b3f0e69ee2b3cd2d81372c81cb5d6308ba81d48b8cc57061ad9b4bdf"
      },
      "candidate_sha": "1e552d675c3795265be8af1ac23ffb61f90f30b1",
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
        "comparison_wall_seconds": 0.2575887069106102,
        "peak_rss_bytes": 13767028736,
        "peak_rss_kib": 13444364,
        "total_worker_wall_seconds": 111.85857847332954,
        "wall_seconds": 111.60098976641893
      },
      "eligible_full": true,
      "evidence_digest": "a8ce498a148a76b19e1a8e2e64347d75f42df5d2d63105455d314741e680dc28",
      "evidence_id": "415bab6b82ef42baa0e0a5277df7aeb9:49937d87a08c533f73470c9dcc48dbc7870c12f467d9a8b5de192dffb5484afa",
      "execution_status": "completed",
      "issues": [],
      "job_id": "415bab6b82ef42baa0e0a5277df7aeb9",
      "metrics": {
        "compilation": 12.756752016022801,
        "forward": 12.382117168977857,
        "gradient": 1.8760113269090652,
        "peak_rss_bytes": 13767028736,
        "runtime": 14.259446823969483,
        "sensitivity": 0.0008984114974737167,
        "setup": 1.0238497275859118,
        "total": 28.040048567578197,
        "transfer": 0.0004199165850877762
      },
      "phases": {
        "build": 0.7346600126475096,
        "forward": 12.382117168977857,
        "forward_compile": 4.924385312944651,
        "forward_lower": 0.870494470000267,
        "gradient": 1.8760113269090652,
        "gradient_compile": 6.096814852207899,
        "gradient_lower": 0.4077671058475971,
        "host_transfer": 0.0004199165850877762,
        "imports": 0.2848028242588043,
        "initialize": 0.0029357559978961945,
        "load": 0.0014511346817016602,
        "sensitivity": 0.0008984114974737167,
        "sensitivity_compile": 0.37297157756984234,
        "sensitivity_lower": 0.08431869745254517
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
          "sampled_process_group_peak_rss_bytes": 13768077312,
          "samples": 437
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
          "differometor/build.py": "f1fdff78515500f5912907537dbedecf30c3915fa949b820bf2ad81b4c062771",
          "differometor/components.py": "2e857e19d468d94b46594f71a76221d9d8b677bad05f6cf03b9e57b0e1613593",
          "differometor/plot.py": "16735e0fb14902f2c024e3da9f2655cbea634c4dd9e06c48af1247e12d0cf606",
          "differometor/setups.py": "478b1a7391b28604c36d8245e13ffa4f6d0f6dc32eeac6c6feaf5c08aa06a76b",
          "differometor/simulate.py": "8225fedb4580e39fcc3f3611e73e4e356c7c0b55e4a3353486fcad9260d77c01",
          "differometor/utils.py": "73ee8a862cbc435363904addc363071ed7dc8b1546956f82e1746998fe3b09ff"
        },
        "worker_sha256": "d3c212da0ab1215187407d9cd21dc2cbb5f88dc0b5ee7885135bf7f002d14b58"
      },
      "validated_output_scope": "last_warm_evaluation",
      "warm_metrics": {
        "forward": 12.542850732803345,
        "gradient": 1.875739123672247,
        "host_transfer": 0.0003086775541305542,
        "sensitivity": 0.21159253269433975
      },
      "worker_error": null
    },
    {
      "artifact_digest": "b547550f15337f868903dbcb118fa79d025993744270cf25cc8c7816a2e5616d",
      "artifact_digests": {
        "comparison.json": "005847678f9babe30a632a5a1a82e2a3edbabb30000bd9d443af41d13038a7d0",
        "report.json": "6b880067010b521f1a4c6071a146d70dbbf321cad9e73d2863b371c6863e950b",
        "result": "d30369d24d849b36c214cb6ee7a1ca78beafd5c6a9dba2ceeed83625ef475246"
      },
      "candidate_sha": "1e552d675c3795265be8af1ac23ffb61f90f30b1",
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
        "comparison_wall_seconds": 0.25682039745151997,
        "peak_rss_bytes": 13758509056,
        "peak_rss_kib": 13436044,
        "total_worker_wall_seconds": 113.93450396507978,
        "wall_seconds": 113.67768356762826
      },
      "eligible_full": true,
      "evidence_digest": "72d952d6f5137b4652e3b687174999ea816a27567db57ec1648422f791769fd4",
      "evidence_id": "882be0c143db470c9686cd2ba9e44c77:b547550f15337f868903dbcb118fa79d025993744270cf25cc8c7816a2e5616d",
      "execution_status": "completed",
      "issues": [],
      "job_id": "882be0c143db470c9686cd2ba9e44c77",
      "metrics": {
        "compilation": 13.170896405354142,
        "forward": 12.400077329948545,
        "gradient": 1.902217959985137,
        "peak_rss_bytes": 13758509056,
        "runtime": 14.30376430414617,
        "sensitivity": 0.0010634586215019226,
        "setup": 1.099603358656168,
        "total": 28.57426406815648,
        "transfer": 0.0004055555909872055
      },
      "phases": {
        "build": 0.8086971193552017,
        "forward": 12.400077329948545,
        "forward_compile": 5.102056432515383,
        "forward_lower": 0.9158173240721226,
        "gradient": 1.902217959985137,
        "gradient_compile": 6.248855207115412,
        "gradient_lower": 0.4496453870087862,
        "host_transfer": 0.0004055555909872055,
        "imports": 0.2865349929779768,
        "initialize": 0.002890240401029587,
        "load": 0.001481005921959877,
        "sensitivity": 0.0010634586215019226,
        "sensitivity_compile": 0.3675619624555111,
        "sensitivity_lower": 0.0869600921869278
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
          "sampled_process_group_peak_rss_bytes": 13759557632,
          "samples": 445
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
          "differometor/build.py": "f1fdff78515500f5912907537dbedecf30c3915fa949b820bf2ad81b4c062771",
          "differometor/components.py": "2e857e19d468d94b46594f71a76221d9d8b677bad05f6cf03b9e57b0e1613593",
          "differometor/plot.py": "16735e0fb14902f2c024e3da9f2655cbea634c4dd9e06c48af1247e12d0cf606",
          "differometor/setups.py": "478b1a7391b28604c36d8245e13ffa4f6d0f6dc32eeac6c6feaf5c08aa06a76b",
          "differometor/simulate.py": "8225fedb4580e39fcc3f3611e73e4e356c7c0b55e4a3353486fcad9260d77c01",
          "differometor/utils.py": "73ee8a862cbc435363904addc363071ed7dc8b1546956f82e1746998fe3b09ff"
        },
        "worker_sha256": "d3c212da0ab1215187407d9cd21dc2cbb5f88dc0b5ee7885135bf7f002d14b58"
      },
      "validated_output_scope": "last_warm_evaluation",
      "warm_metrics": {
        "forward": 12.743575628846884,
        "gradient": 1.8781429361552,
        "host_transfer": 0.00023546814918518066,
        "sensitivity": 0.2108212560415268
      },
      "worker_error": null
    },
    {
      "artifact_digest": "820c7dfc19d0099d62f3b2315da0fb1dd7ee7ee9203b875447cfc2bd07d956a2",
      "artifact_digests": {
        "comparison.json": "005847678f9babe30a632a5a1a82e2a3edbabb30000bd9d443af41d13038a7d0",
        "report.json": "b2edb193ca235a5cd902e415ddbad328d0cce85c3c44f193a72c3f4ea10409d2",
        "result": "c7b4f4d5f713d1efa4ad20c9f07ef304bb352c40b55052971c2251f12bcd3b42"
      },
      "candidate_sha": "1e552d675c3795265be8af1ac23ffb61f90f30b1",
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
        "comparison_wall_seconds": 0.25740163773298264,
        "peak_rss_bytes": 13754388480,
        "peak_rss_kib": 13432020,
        "total_worker_wall_seconds": 111.85716444440186,
        "wall_seconds": 111.59976280666888
      },
      "eligible_full": true,
      "evidence_digest": "e06feb15f7c2ba1e21aa1fa63f7a879f1b3784912b5b2a6d879930c01a887e22",
      "evidence_id": "e6e5badb945c47ae927e511a3ff15fd7:820c7dfc19d0099d62f3b2315da0fb1dd7ee7ee9203b875447cfc2bd07d956a2",
      "execution_status": "completed",
      "issues": [],
      "job_id": "e6e5badb945c47ae927e511a3ff15fd7",
      "metrics": {
        "compilation": 12.777620123699307,
        "forward": 12.399473497644067,
        "gradient": 1.8828602991998196,
        "peak_rss_bytes": 13754388480,
        "runtime": 14.283548314124346,
        "sensitivity": 0.0009176898747682571,
        "setup": 1.032353088259697,
        "total": 28.09352152608335,
        "transfer": 0.00029682740569114685
      },
      "phases": {
        "build": 0.7394567411392927,
        "forward": 12.399473497644067,
        "forward_compile": 4.945773968473077,
        "forward_lower": 0.8744982127100229,
        "gradient": 1.8828602991998196,
        "gradient_compile": 6.078064216300845,
        "gradient_lower": 0.41370727121829987,
        "host_transfer": 0.00029682740569114685,
        "imports": 0.2885946538299322,
        "initialize": 0.002883758395910263,
        "load": 0.0014179348945617676,
        "sensitivity": 0.0009176898747682571,
        "sensitivity_compile": 0.379582442343235,
        "sensitivity_lower": 0.08599401265382767
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
          "sampled_process_group_peak_rss_bytes": 13755437056,
          "samples": 437
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
          "differometor/build.py": "f1fdff78515500f5912907537dbedecf30c3915fa949b820bf2ad81b4c062771",
          "differometor/components.py": "2e857e19d468d94b46594f71a76221d9d8b677bad05f6cf03b9e57b0e1613593",
          "differometor/plot.py": "16735e0fb14902f2c024e3da9f2655cbea634c4dd9e06c48af1247e12d0cf606",
          "differometor/setups.py": "478b1a7391b28604c36d8245e13ffa4f6d0f6dc32eeac6c6feaf5c08aa06a76b",
          "differometor/simulate.py": "8225fedb4580e39fcc3f3611e73e4e356c7c0b55e4a3353486fcad9260d77c01",
          "differometor/utils.py": "73ee8a862cbc435363904addc363071ed7dc8b1546956f82e1746998fe3b09ff"
        },
        "worker_sha256": "d3c212da0ab1215187407d9cd21dc2cbb5f88dc0b5ee7885135bf7f002d14b58"
      },
      "validated_output_scope": "last_warm_evaluation",
      "warm_metrics": {
        "forward": 12.515215031802654,
        "gradient": 1.8746604043990374,
        "host_transfer": 0.0002299882471561432,
        "sensitivity": 0.20756630413234234
      },
      "worker_error": null
    }
  ],
  "evidence_ids": [
    "415bab6b82ef42baa0e0a5277df7aeb9:49937d87a08c533f73470c9dcc48dbc7870c12f467d9a8b5de192dffb5484afa",
    "882be0c143db470c9686cd2ba9e44c77:b547550f15337f868903dbcb118fa79d025993744270cf25cc8c7816a2e5616d",
    "e6e5badb945c47ae927e511a3ff15fd7:820c7dfc19d0099d62f3b2315da0fb1dd7ee7ee9203b875447cfc2bd07d956a2"
  ],
  "git_parents": null,
  "heuristic_id": null,
  "hypothesis": null,
  "improved": false,
  "kind": "seed",
  "lane_id": "discrete",
  "metrics": {
    "compilation": 12.777620123699307,
    "forward": 12.399473497644067,
    "gradient": 1.8828602991998196,
    "peak_rss_bytes": 13758509056,
    "runtime": 14.283548314124346,
    "sensitivity": 0.0009176898747682571,
    "setup": 1.032353088259697,
    "total": 28.09352152608335,
    "transfer": 0.0004055555909872055
  },
  "model_manifest": null,
  "owner": "coordinator",
  "owner_version": 1,
  "parameters": {
    "checkpoint": true,
    "map_batch_size": null,
    "prevent_cse": false
  },
  "parameters_after": {
    "checkpoint": true,
    "map_batch_size": null,
    "prevent_cse": false
  },
  "parameters_before": null,
  "parents": [],
  "prompt_sha256": null,
  "proposal": {
    "candidate_id": "seed8",
    "commit_sha": "1e552d675c3795265be8af1ac23ffb61f90f30b1",
    "content_sha256": "8225fedb4580e39fcc3f3611e73e4e356c7c0b55e4a3353486fcad9260d77c01",
    "kind": "seed",
    "lane_id": "discrete",
    "parameters": {
      "checkpoint": true,
      "map_batch_size": null,
      "prevent_cse": false
    },
    "parents": [],
    "proposal_id": "seed8",
    "provenance": {
      "heuristic_id": "import-confirmed-strong-agent-seed",
      "model": "validated Codex seed8, three fresh full measurements"
    },
    "recipe": null,
    "round_id": "round-001"
  },
  "proposal_id": "seed8",
  "provenance": {
    "heuristic_id": "import-confirmed-strong-agent-seed",
    "model": "validated Codex seed8, three fresh full measurements"
  },
  "recipe": null,
  "response_sha256": null,
  "round_id": "round-001",
  "target_symbols": null,
  "uncertainty": "No repeat-confirmation or causality is inferred from this export. Inspect exact job evidence and matching cohorts.",
  "valid": true
}
```

### import-42aaabf394d2d9bf5618b6802eb1e11315e85030

```json
{
  "cohort_digest": "10567ad0f8dcb7122b6b182e1be342313b89eef340d4070073fdf62d6342204c",
  "commit_sha": "42aaabf394d2d9bf5618b6802eb1e11315e85030",
  "content_sha256": "ca7a299118fe3731c494910ae92526d3ed4c82ee4924a38380c2dc75c1463b19",
  "context_sha256": null,
  "evaluation_requests": [
    {
      "attempt": 1,
      "candidate_id": "import-42aaabf394d2d9bf5618b6802eb1e11315e85030",
      "evidence_id": "7f9a3863201d4908b9e2607e8b925bdc:70e1da46befd5d0fd365188a88a91391f95e2df62042e7a6687de8abbaf8c611",
      "imported": true,
      "job_id": "7f9a3863201d4908b9e2607e8b925bdc",
      "profile": "full",
      "request_id": "9986889c8d0f4e20bf78c21cdbb7423e",
      "status": "valid"
    }
  ],
  "evidence": [
    {
      "artifact_digest": "70e1da46befd5d0fd365188a88a91391f95e2df62042e7a6687de8abbaf8c611",
      "artifact_digests": {
        "comparison.json": "005847678f9babe30a632a5a1a82e2a3edbabb30000bd9d443af41d13038a7d0",
        "report.json": "99b11631ac61d413d7f19004db5545450cd93405d07cea2955d04cc5405711af",
        "result": "0a722ff95fd89fac3abbb76e680b29fa417654284b72ae5c5db7004536db19c8"
      },
      "candidate_sha": "42aaabf394d2d9bf5618b6802eb1e11315e85030",
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
        "comparison_wall_seconds": 0.26017045602202415,
        "peak_rss_bytes": 13758693376,
        "peak_rss_kib": 13436224,
        "total_worker_wall_seconds": 112.69091638363898,
        "wall_seconds": 112.43074592761695
      },
      "eligible_full": true,
      "evidence_digest": "4a2d74726409a39254b78e01905db339de328515277cc50ea018f0f86dc2667b",
      "evidence_id": "7f9a3863201d4908b9e2607e8b925bdc:70e1da46befd5d0fd365188a88a91391f95e2df62042e7a6687de8abbaf8c611",
      "execution_status": "completed",
      "issues": [],
      "job_id": "7f9a3863201d4908b9e2607e8b925bdc",
      "metrics": {
        "compilation": 13.072265705093741,
        "forward": 12.629501961171627,
        "gradient": 1.8934158831834793,
        "peak_rss_bytes": 13758693376,
        "runtime": 14.524255460128188,
        "sensitivity": 0.0009246896952390671,
        "setup": 1.0512448493391275,
        "total": 28.647766014561057,
        "transfer": 0.0004129260778427124
      },
      "phases": {
        "build": 0.7617828771471977,
        "forward": 12.629501961171627,
        "forward_compile": 4.96721850335598,
        "forward_lower": 0.8655092362314463,
        "gradient": 1.8934158831834793,
        "gradient_compile": 6.274708459153771,
        "gradient_lower": 0.4280959088355303,
        "host_transfer": 0.0004129260778427124,
        "imports": 0.28519229404628277,
        "initialize": 0.002861395478248596,
        "load": 0.0014082826673984528,
        "sensitivity": 0.0009246896952390671,
        "sensitivity_compile": 0.4373494014143944,
        "sensitivity_lower": 0.09938419610261917
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
          "sampled_process_group_peak_rss_bytes": 13759741952,
          "samples": 436
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
          "differometor/build.py": "f1fdff78515500f5912907537dbedecf30c3915fa949b820bf2ad81b4c062771",
          "differometor/components.py": "2e857e19d468d94b46594f71a76221d9d8b677bad05f6cf03b9e57b0e1613593",
          "differometor/plot.py": "16735e0fb14902f2c024e3da9f2655cbea634c4dd9e06c48af1247e12d0cf606",
          "differometor/setups.py": "478b1a7391b28604c36d8245e13ffa4f6d0f6dc32eeac6c6feaf5c08aa06a76b",
          "differometor/simulate.py": "ca7a299118fe3731c494910ae92526d3ed4c82ee4924a38380c2dc75c1463b19",
          "differometor/utils.py": "73ee8a862cbc435363904addc363071ed7dc8b1546956f82e1746998fe3b09ff"
        },
        "worker_sha256": "d3c212da0ab1215187407d9cd21dc2cbb5f88dc0b5ee7885135bf7f002d14b58"
      },
      "validated_output_scope": "last_warm_evaluation",
      "warm_metrics": {
        "forward": 12.641886975616217,
        "gradient": 1.8898078352212906,
        "host_transfer": 0.00025232695043087006,
        "sensitivity": 0.2136995568871498
      },
      "worker_error": null
    }
  ],
  "evidence_ids": [
    "7f9a3863201d4908b9e2607e8b925bdc:70e1da46befd5d0fd365188a88a91391f95e2df62042e7a6687de8abbaf8c611"
  ],
  "git_parents": null,
  "heuristic_id": null,
  "hypothesis": null,
  "improved": false,
  "kind": "seed",
  "lane_id": "discrete",
  "metrics": {
    "compilation": 13.072265705093741,
    "forward": 12.629501961171627,
    "gradient": 1.8934158831834793,
    "peak_rss_bytes": 13758693376,
    "runtime": 14.524255460128188,
    "sensitivity": 0.0009246896952390671,
    "setup": 1.0512448493391275,
    "total": 28.647766014561057,
    "transfer": 0.0004129260778427124
  },
  "model_manifest": null,
  "owner": "coordinator",
  "owner_version": 1,
  "parameters": {
    "checkpoint": true,
    "map_batch_size": null,
    "prevent_cse": true
  },
  "parameters_after": {
    "checkpoint": true,
    "map_batch_size": null,
    "prevent_cse": true
  },
  "parameters_before": null,
  "parents": [],
  "prompt_sha256": null,
  "proposal": {
    "candidate_id": "import-42aaabf394d2d9bf5618b6802eb1e11315e85030",
    "commit_sha": "42aaabf394d2d9bf5618b6802eb1e11315e85030",
    "content_sha256": "ca7a299118fe3731c494910ae92526d3ed4c82ee4924a38380c2dc75c1463b19",
    "kind": "seed",
    "lane_id": "discrete",
    "parameters": {
      "checkpoint": true,
      "map_batch_size": null,
      "prevent_cse": true
    },
    "parents": [],
    "proposal_id": "import-42aaabf394d2d9bf5618b6802eb1e11315e85030",
    "provenance": {
      "heuristic_id": "import-exact-full-evidence",
      "model_calls": 0,
      "source_branch": "explore/dag-pilot-v1",
      "source_job": "7f9a3863201d4908b9e2607e8b925bdc"
    },
    "recipe": null,
    "round_id": "round-001"
  },
  "proposal_id": "import-42aaabf394d2d9bf5618b6802eb1e11315e85030",
  "provenance": {
    "heuristic_id": "import-exact-full-evidence",
    "model_calls": 0,
    "source_branch": "explore/dag-pilot-v1",
    "source_job": "7f9a3863201d4908b9e2607e8b925bdc"
  },
  "recipe": null,
  "response_sha256": null,
  "round_id": "round-001",
  "target_symbols": null,
  "uncertainty": "No repeat-confirmation or causality is inferred from this export. Inspect exact job evidence and matching cohorts.",
  "valid": true
}
```

### 78273c30837743b594ef628e5c0056f2

```json
{
  "cohort_digest": "10567ad0f8dcb7122b6b182e1be342313b89eef340d4070073fdf62d6342204c",
  "commit_sha": "2994693a064e90850c710bd3b3f3317ba525f81b",
  "content_sha256": "74f7b8428777d855961a096ad89bf59d1e6703929e489339428dc1ae645f4342",
  "context_sha256": null,
  "evaluation_requests": [
    {
      "attempt": 1,
      "candidate_id": "78273c30837743b594ef628e5c0056f2",
      "evidence_id": "5b3af3628df54f778c117ffaad033a5e:34f77add4e58cd3f92f928160be72ce5d3350ed3868f51fb1e1c1a0fc5e1c9c9",
      "imported": false,
      "job_id": "5b3af3628df54f778c117ffaad033a5e",
      "profile": "screen",
      "request_id": "1b702666abb64c298300b48af3e5bf4a",
      "status": "screen"
    },
    {
      "attempt": 1,
      "candidate_id": "78273c30837743b594ef628e5c0056f2",
      "evidence_id": "cde035e7126e4e00a4eccc5192f41d86:97a7e880e414101b6593ca85de16889e7fe6e0c28c1e57ad796fb9a0660824be",
      "imported": false,
      "job_id": "cde035e7126e4e00a4eccc5192f41d86",
      "profile": "full",
      "request_id": "4232037f6ce9412b8a1978d5f0126815",
      "status": "valid"
    }
  ],
  "evidence": [
    {
      "artifact_digest": "34f77add4e58cd3f92f928160be72ce5d3350ed3868f51fb1e1c1a0fc5e1c9c9",
      "artifact_digests": {
        "report.json": "321545e1d219f0d28e057881d01877cc9a4ffce8962182b9a46858ec4c164637",
        "result": "b36bed355a07b02b835faff0b87b7df1c48676491a44c785dff798fae610c9ba"
      },
      "candidate_sha": "2994693a064e90850c710bd3b3f3317ba525f81b",
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
        "peak_rss_bytes": 13892165632,
        "peak_rss_kib": 13566568,
        "total_worker_wall_seconds": 38.192525347694755,
        "wall_seconds": 38.192525347694755
      },
      "eligible_full": false,
      "evidence_digest": "40e86809fff8a83ae355f3bb1361aa7671e13f44c8fcd973859ceb0b360e6bfe",
      "evidence_id": "5b3af3628df54f778c117ffaad033a5e:34f77add4e58cd3f92f928160be72ce5d3350ed3868f51fb1e1c1a0fc5e1c9c9",
      "execution_status": "completed",
      "issues": [],
      "job_id": "5b3af3628df54f778c117ffaad033a5e",
      "metrics": {
        "compilation": 20.801648339256644,
        "forward": 12.410376146435738,
        "gradient": 2.702880498021841,
        "peak_rss_bytes": 13892165632,
        "runtime": 15.114624256268144,
        "sensitivity": 0.0009342581033706665,
        "setup": 1.0515214279294014,
        "total": 36.96779402345419,
        "transfer": 0.0004333537071943283
      },
      "phases": {
        "build": 0.753487603738904,
        "forward": 12.410376146435738,
        "forward_compile": 6.44573044963181,
        "forward_lower": 1.0272200796753168,
        "gradient": 2.702880498021841,
        "gradient_compile": 12.43188852071762,
        "gradient_lower": 0.4178471826016903,
        "host_transfer": 0.0004333537071943283,
        "imports": 0.2936037741601467,
        "initialize": 0.0029286853969097137,
        "load": 0.0015013646334409714,
        "sensitivity": 0.0009342581033706665,
        "sensitivity_compile": 0.3893319386988878,
        "sensitivity_lower": 0.08963016793131828
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
          "sampled_process_group_peak_rss_bytes": 13683499008,
          "samples": 148
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
          "differometor/build.py": "f1fdff78515500f5912907537dbedecf30c3915fa949b820bf2ad81b4c062771",
          "differometor/components.py": "2e857e19d468d94b46594f71a76221d9d8b677bad05f6cf03b9e57b0e1613593",
          "differometor/plot.py": "16735e0fb14902f2c024e3da9f2655cbea634c4dd9e06c48af1247e12d0cf606",
          "differometor/setups.py": "478b1a7391b28604c36d8245e13ffa4f6d0f6dc32eeac6c6feaf5c08aa06a76b",
          "differometor/simulate.py": "74f7b8428777d855961a096ad89bf59d1e6703929e489339428dc1ae645f4342",
          "differometor/utils.py": "73ee8a862cbc435363904addc363071ed7dc8b1546956f82e1746998fe3b09ff"
        },
        "worker_sha256": "d3c212da0ab1215187407d9cd21dc2cbb5f88dc0b5ee7885135bf7f002d14b58"
      },
      "validated_output_scope": "first_evaluation",
      "warm_metrics": {},
      "worker_error": null
    },
    {
      "artifact_digest": "97a7e880e414101b6593ca85de16889e7fe6e0c28c1e57ad796fb9a0660824be",
      "artifact_digests": {
        "comparison.json": "14cee258d15cfb2281f4ae761fc590bc56d1af633055a1fc324296c2a9b781fa",
        "report.json": "6d86f368a274f747f7e84a7b7e881a504cfdf32eec0232a602e871c00c3aeee3",
        "result": "383bbd5517a259b8ad264be11cb1f2f45556df2573a11ba6d7edeaa31a8488f9"
      },
      "candidate_sha": "2994693a064e90850c710bd3b3f3317ba525f81b",
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
        "comparison_wall_seconds": 0.2613643053919077,
        "peak_rss_bytes": 14032572416,
        "peak_rss_kib": 13703684,
        "total_worker_wall_seconds": 124.03257509320974,
        "wall_seconds": 123.77121078781784
      },
      "eligible_full": true,
      "evidence_digest": "abcc12074cde799c4e766ec7f97436a8715449f291b6c1adffc03924b85215f7",
      "evidence_id": "cde035e7126e4e00a4eccc5192f41d86:97a7e880e414101b6593ca85de16889e7fe6e0c28c1e57ad796fb9a0660824be",
      "execution_status": "completed",
      "issues": [],
      "job_id": "cde035e7126e4e00a4eccc5192f41d86",
      "metrics": {
        "compilation": 20.671813905239105,
        "forward": 12.41929541528225,
        "gradient": 2.7039095647633076,
        "peak_rss_bytes": 14032572416,
        "runtime": 15.124528743326664,
        "sensitivity": 0.0008589997887611389,
        "setup": 1.047775287181139,
        "total": 36.84411793574691,
        "transfer": 0.00046476349234580994
      },
      "phases": {
        "build": 0.748774915933609,
        "forward": 12.41929541528225,
        "forward_compile": 6.488020375370979,
        "forward_lower": 1.0782733708620071,
        "gradient": 2.7039095647633076,
        "gradient_compile": 12.20796892233193,
        "gradient_lower": 0.416846189647913,
        "host_transfer": 0.00046476349234580994,
        "imports": 0.29462870210409164,
        "initialize": 0.002879556268453598,
        "load": 0.0014921128749847412,
        "sensitivity": 0.0008589997887611389,
        "sensitivity_compile": 0.39016303792595863,
        "sensitivity_lower": 0.09054200910031796
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
          "sampled_process_group_peak_rss_bytes": 13961269248,
          "samples": 480
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
          "differometor/build.py": "f1fdff78515500f5912907537dbedecf30c3915fa949b820bf2ad81b4c062771",
          "differometor/components.py": "2e857e19d468d94b46594f71a76221d9d8b677bad05f6cf03b9e57b0e1613593",
          "differometor/plot.py": "16735e0fb14902f2c024e3da9f2655cbea634c4dd9e06c48af1247e12d0cf606",
          "differometor/setups.py": "478b1a7391b28604c36d8245e13ffa4f6d0f6dc32eeac6c6feaf5c08aa06a76b",
          "differometor/simulate.py": "74f7b8428777d855961a096ad89bf59d1e6703929e489339428dc1ae645f4342",
          "differometor/utils.py": "73ee8a862cbc435363904addc363071ed7dc8b1546956f82e1746998fe3b09ff"
        },
        "worker_sha256": "d3c212da0ab1215187407d9cd21dc2cbb5f88dc0b5ee7885135bf7f002d14b58"
      },
      "validated_output_scope": "last_warm_evaluation",
      "warm_metrics": {
        "forward": 12.589301971718669,
        "gradient": 2.4600441101938486,
        "host_transfer": 0.0002547968178987503,
        "sensitivity": 0.2143464107066393
      },
      "worker_error": null
    }
  ],
  "evidence_ids": [
    "5b3af3628df54f778c117ffaad033a5e:34f77add4e58cd3f92f928160be72ce5d3350ed3868f51fb1e1c1a0fc5e1c9c9",
    "cde035e7126e4e00a4eccc5192f41d86:97a7e880e414101b6593ca85de16889e7fe6e0c28c1e57ad796fb9a0660824be"
  ],
  "git_parents": null,
  "heuristic_id": null,
  "hypothesis": null,
  "improved": false,
  "kind": "mutate",
  "lane_id": "discrete",
  "metrics": {
    "compilation": 20.671813905239105,
    "forward": 12.41929541528225,
    "gradient": 2.7039095647633076,
    "peak_rss_bytes": 14032572416,
    "runtime": 15.124528743326664,
    "sensitivity": 0.0008589997887611389,
    "setup": 1.047775287181139,
    "total": 36.84411793574691,
    "transfer": 0.00046476349234580994
  },
  "model_manifest": null,
  "owner": "coordinator",
  "owner_version": 1,
  "parameters": {
    "checkpoint": true,
    "map_batch_size": 1,
    "prevent_cse": false
  },
  "parameters_after": {
    "checkpoint": true,
    "map_batch_size": 1,
    "prevent_cse": false
  },
  "parameters_before": null,
  "parents": [
    "seed8"
  ],
  "prompt_sha256": null,
  "proposal": {
    "candidate_id": "78273c30837743b594ef628e5c0056f2",
    "commit_sha": "2994693a064e90850c710bd3b3f3317ba525f81b",
    "content_sha256": "74f7b8428777d855961a096ad89bf59d1e6703929e489339428dc1ae645f4342",
    "kind": "mutate",
    "lane_id": "discrete",
    "parameters": {
      "checkpoint": true,
      "map_batch_size": 1,
      "prevent_cse": false
    },
    "parents": [
      "seed8"
    ],
    "proposal_id": "78273c30837743b594ef628e5c0056f2",
    "provenance": {
      "acceptance": {
        "absolute_seconds": 0.02,
        "noise_guard": "maximum observed range of both candidates",
        "relative": 0.01
      },
      "context": {
        "bytes": 2167,
        "path": "contexts/2092dd69a74463dcbb5e673c8548d722ee879145d57a12218f27a8d65070c13f.json",
        "sha256": "2092dd69a74463dcbb5e673c8548d722ee879145d57a12218f27a8d65070c13f"
      },
      "context_sha256": "2092dd69a74463dcbb5e673c8548d722ee879145d57a12218f27a8d65070c13f",
      "controller_commit": "5549b087ed6433a8af9a0cde4212e1f5f1ec5b5b",
      "git_parent_sha": "79a5c3233d32aa14672004ac152dfda2ba5c9630",
      "heuristic_id": "discrete-search-v1-local-search",
      "hypothesis": "Measure registered configuration using local-search at categorical distance 1 from the noise-qualified incumbent; improvement is unmeasured.",
      "incumbent_candidate": "seed8",
      "model_calls": 0,
      "neighborhood_radius": 1,
      "operator_version": "seed8-component-execution-v1",
      "parameters_before": {
        "checkpoint": true,
        "map_batch_size": null,
        "prevent_cse": false
      },
      "remaining_configurations": 13,
      "target_symbols": [
        "simulate._evaluate_component",
        "simulate.update"
      ]
    },
    "recipe": "discrete",
    "round_id": "round-001"
  },
  "proposal_id": "78273c30837743b594ef628e5c0056f2",
  "provenance": {
    "acceptance": {
      "absolute_seconds": 0.02,
      "noise_guard": "maximum observed range of both candidates",
      "relative": 0.01
    },
    "context": {
      "bytes": 2167,
      "path": "contexts/2092dd69a74463dcbb5e673c8548d722ee879145d57a12218f27a8d65070c13f.json",
      "sha256": "2092dd69a74463dcbb5e673c8548d722ee879145d57a12218f27a8d65070c13f"
    },
    "context_sha256": "2092dd69a74463dcbb5e673c8548d722ee879145d57a12218f27a8d65070c13f",
    "controller_commit": "5549b087ed6433a8af9a0cde4212e1f5f1ec5b5b",
    "git_parent_sha": "79a5c3233d32aa14672004ac152dfda2ba5c9630",
    "heuristic_id": "discrete-search-v1-local-search",
    "hypothesis": "Measure registered configuration using local-search at categorical distance 1 from the noise-qualified incumbent; improvement is unmeasured.",
    "incumbent_candidate": "seed8",
    "model_calls": 0,
    "neighborhood_radius": 1,
    "operator_version": "seed8-component-execution-v1",
    "parameters_before": {
      "checkpoint": true,
      "map_batch_size": null,
      "prevent_cse": false
    },
    "remaining_configurations": 13,
    "target_symbols": [
      "simulate._evaluate_component",
      "simulate.update"
    ]
  },
  "recipe": "discrete",
  "response_sha256": null,
  "round_id": "round-001",
  "target_symbols": null,
  "uncertainty": "No repeat-confirmation or causality is inferred from this export. Inspect exact job evidence and matching cohorts.",
  "valid": true
}
```

### 1480647fdf514cc7a7a47e78c11dbfbb

```json
{
  "cohort_digest": "10567ad0f8dcb7122b6b182e1be342313b89eef340d4070073fdf62d6342204c",
  "commit_sha": "0955a78b6b96a3aba4bc3eeb1649b211ebf314c1",
  "content_sha256": "56bccc56bb0c5722f6e84cafd63135f7ed19f650ec8c3e49baa03e148dfa45b9",
  "context_sha256": null,
  "evaluation_requests": [
    {
      "attempt": 1,
      "candidate_id": "1480647fdf514cc7a7a47e78c11dbfbb",
      "evidence_id": "f1c5134330144123bf6a90b7d712a544:663b207a2fd05652d225a8e39268e3768d8906f21c2b46fabb5257540816bac4",
      "imported": false,
      "job_id": "f1c5134330144123bf6a90b7d712a544",
      "profile": "screen",
      "request_id": "753a2cdb52ab484fb7826d23fd14ed93",
      "status": "screen"
    },
    {
      "attempt": 1,
      "candidate_id": "1480647fdf514cc7a7a47e78c11dbfbb",
      "evidence_id": "8d433ae433e5496b89cb4de587c0862f:e73ec4d8e0e0b141c91c65a03e7de4e446cb51042c5f42264060bcc887a94bbf",
      "imported": false,
      "job_id": "8d433ae433e5496b89cb4de587c0862f",
      "profile": "full",
      "request_id": "faff7d74001d46d38ed0ea288e4ac0ac",
      "status": "valid"
    }
  ],
  "evidence": [
    {
      "artifact_digest": "663b207a2fd05652d225a8e39268e3768d8906f21c2b46fabb5257540816bac4",
      "artifact_digests": {
        "report.json": "441ba0c197f3435b4ba5638695301a5dabd0003c319bd32fc1450a198ff6392b",
        "result": "6cf0241007252c91420ed0b7d504fe1244bf0bc6d08c097f32e456f529896d95"
      },
      "candidate_sha": "0955a78b6b96a3aba4bc3eeb1649b211ebf314c1",
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
        "peak_rss_bytes": 14106091520,
        "peak_rss_kib": 13775480,
        "total_worker_wall_seconds": 51.328615771606565,
        "wall_seconds": 51.328615771606565
      },
      "eligible_full": false,
      "evidence_digest": "3212e94f1e5d0f47301ce42079a3ce54feb0e504788f4b309ec987ee23578213",
      "evidence_id": "f1c5134330144123bf6a90b7d712a544:663b207a2fd05652d225a8e39268e3768d8906f21c2b46fabb5257540816bac4",
      "execution_status": "completed",
      "issues": [],
      "job_id": "f1c5134330144123bf6a90b7d712a544",
      "metrics": {
        "compilation": 33.906549513339996,
        "forward": 12.405555743724108,
        "gradient": 2.5363154988735914,
        "peak_rss_bytes": 14106091520,
        "runtime": 14.943289075046778,
        "sensitivity": 0.0010376758873462677,
        "setup": 1.0410551130771637,
        "total": 49.89089370146394,
        "transfer": 0.0003801565617322922
      },
      "phases": {
        "build": 0.7478495985269547,
        "forward": 12.405555743724108,
        "forward_compile": 10.28999949991703,
        "forward_lower": 1.524541713297367,
        "gradient": 2.5363154988735914,
        "gradient_compile": 20.893605194985867,
        "gradient_lower": 0.7125048916786909,
        "host_transfer": 0.0003801565617322922,
        "imports": 0.2888498604297638,
        "initialize": 0.002878548577427864,
        "load": 0.0014771055430173874,
        "sensitivity": 0.0010376758873462677,
        "sensitivity_compile": 0.39023981615900993,
        "sensitivity_lower": 0.09565839730203152
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
          "sampled_process_group_peak_rss_bytes": 14023254016,
          "samples": 199
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
          "differometor/build.py": "f1fdff78515500f5912907537dbedecf30c3915fa949b820bf2ad81b4c062771",
          "differometor/components.py": "2e857e19d468d94b46594f71a76221d9d8b677bad05f6cf03b9e57b0e1613593",
          "differometor/plot.py": "16735e0fb14902f2c024e3da9f2655cbea634c4dd9e06c48af1247e12d0cf606",
          "differometor/setups.py": "478b1a7391b28604c36d8245e13ffa4f6d0f6dc32eeac6c6feaf5c08aa06a76b",
          "differometor/simulate.py": "56bccc56bb0c5722f6e84cafd63135f7ed19f650ec8c3e49baa03e148dfa45b9",
          "differometor/utils.py": "73ee8a862cbc435363904addc363071ed7dc8b1546956f82e1746998fe3b09ff"
        },
        "worker_sha256": "d3c212da0ab1215187407d9cd21dc2cbb5f88dc0b5ee7885135bf7f002d14b58"
      },
      "validated_output_scope": "first_evaluation",
      "warm_metrics": {},
      "worker_error": null
    },
    {
      "artifact_digest": "e73ec4d8e0e0b141c91c65a03e7de4e446cb51042c5f42264060bcc887a94bbf",
      "artifact_digests": {
        "comparison.json": "14cee258d15cfb2281f4ae761fc590bc56d1af633055a1fc324296c2a9b781fa",
        "report.json": "797c1826ac48685784355ce1131ffee42b72b3ef2ba2ecb83cb26645537e4cec",
        "result": "531b3505bb9f03cdfa0bd2493db7250be68995dca6f77ab64673a9712ff53a5a"
      },
      "candidate_sha": "0955a78b6b96a3aba4bc3eeb1649b211ebf314c1",
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
        "comparison_wall_seconds": 0.2599518708884716,
        "peak_rss_bytes": 14304243712,
        "peak_rss_kib": 13968988,
        "total_worker_wall_seconds": 140.6302219275385,
        "wall_seconds": 140.37027005665004
      },
      "eligible_full": true,
      "evidence_digest": "b1fbbb7be5d33412dd972fdebf85a3c00f8a5acf3727cdbd955e24ac1c30debf",
      "evidence_id": "8d433ae433e5496b89cb4de587c0862f:e73ec4d8e0e0b141c91c65a03e7de4e446cb51042c5f42264060bcc887a94bbf",
      "execution_status": "completed",
      "issues": [],
      "job_id": "8d433ae433e5496b89cb4de587c0862f",
      "metrics": {
        "compilation": 33.995546746999025,
        "forward": 12.388441178947687,
        "gradient": 2.777918366715312,
        "peak_rss_bytes": 14304243712,
        "runtime": 15.16760652884841,
        "sensitivity": 0.0009040478616952896,
        "setup": 1.0337322279810905,
        "total": 50.196885503828526,
        "transfer": 0.00034293532371520996
      },
      "phases": {
        "build": 0.7425025589764118,
        "forward": 12.388441178947687,
        "forward_compile": 10.302644226700068,
        "forward_lower": 1.5468241553753614,
        "gradient": 2.777918366715312,
        "gradient_compile": 20.9270563069731,
        "gradient_lower": 0.7372708357870579,
        "host_transfer": 0.00034293532371520996,
        "imports": 0.28691351041197777,
        "initialize": 0.0028950460255146027,
        "load": 0.0014211125671863556,
        "sensitivity": 0.0009040478616952896,
        "sensitivity_compile": 0.3865437861531973,
        "sensitivity_lower": 0.09520743601024151
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
          "sampled_process_group_peak_rss_bytes": 14305292288,
          "samples": 544
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
          "differometor/build.py": "f1fdff78515500f5912907537dbedecf30c3915fa949b820bf2ad81b4c062771",
          "differometor/components.py": "2e857e19d468d94b46594f71a76221d9d8b677bad05f6cf03b9e57b0e1613593",
          "differometor/plot.py": "16735e0fb14902f2c024e3da9f2655cbea634c4dd9e06c48af1247e12d0cf606",
          "differometor/setups.py": "478b1a7391b28604c36d8245e13ffa4f6d0f6dc32eeac6c6feaf5c08aa06a76b",
          "differometor/simulate.py": "56bccc56bb0c5722f6e84cafd63135f7ed19f650ec8c3e49baa03e148dfa45b9",
          "differometor/utils.py": "73ee8a862cbc435363904addc363071ed7dc8b1546956f82e1746998fe3b09ff"
        },
        "worker_sha256": "d3c212da0ab1215187407d9cd21dc2cbb5f88dc0b5ee7885135bf7f002d14b58"
      },
      "validated_output_scope": "last_warm_evaluation",
      "warm_metrics": {
        "forward": 12.560816137120128,
        "gradient": 2.451625507324934,
        "host_transfer": 0.00027290545403957367,
        "sensitivity": 0.21060039289295673
      },
      "worker_error": null
    }
  ],
  "evidence_ids": [
    "f1c5134330144123bf6a90b7d712a544:663b207a2fd05652d225a8e39268e3768d8906f21c2b46fabb5257540816bac4",
    "8d433ae433e5496b89cb4de587c0862f:e73ec4d8e0e0b141c91c65a03e7de4e446cb51042c5f42264060bcc887a94bbf"
  ],
  "git_parents": null,
  "heuristic_id": null,
  "hypothesis": null,
  "improved": false,
  "kind": "mutate",
  "lane_id": "discrete",
  "metrics": {
    "compilation": 33.995546746999025,
    "forward": 12.388441178947687,
    "gradient": 2.777918366715312,
    "peak_rss_bytes": 14304243712,
    "runtime": 15.16760652884841,
    "sensitivity": 0.0009040478616952896,
    "setup": 1.0337322279810905,
    "total": 50.196885503828526,
    "transfer": 0.00034293532371520996
  },
  "model_manifest": null,
  "owner": "coordinator",
  "owner_version": 1,
  "parameters": {
    "checkpoint": true,
    "map_batch_size": 2,
    "prevent_cse": false
  },
  "parameters_after": {
    "checkpoint": true,
    "map_batch_size": 2,
    "prevent_cse": false
  },
  "parameters_before": null,
  "parents": [
    "seed8"
  ],
  "prompt_sha256": null,
  "proposal": {
    "candidate_id": "1480647fdf514cc7a7a47e78c11dbfbb",
    "commit_sha": "0955a78b6b96a3aba4bc3eeb1649b211ebf314c1",
    "content_sha256": "56bccc56bb0c5722f6e84cafd63135f7ed19f650ec8c3e49baa03e148dfa45b9",
    "kind": "mutate",
    "lane_id": "discrete",
    "parameters": {
      "checkpoint": true,
      "map_batch_size": 2,
      "prevent_cse": false
    },
    "parents": [
      "seed8"
    ],
    "proposal_id": "1480647fdf514cc7a7a47e78c11dbfbb",
    "provenance": {
      "acceptance": {
        "absolute_seconds": 0.02,
        "noise_guard": "maximum observed range of both candidates",
        "relative": 0.01
      },
      "context": {
        "bytes": 2528,
        "path": "contexts/94312dad4150a4daf58e4e678df02bba0ec10f70964d29def667396487ac6a4a.json",
        "sha256": "94312dad4150a4daf58e4e678df02bba0ec10f70964d29def667396487ac6a4a"
      },
      "context_sha256": "94312dad4150a4daf58e4e678df02bba0ec10f70964d29def667396487ac6a4a",
      "controller_commit": "5549b087ed6433a8af9a0cde4212e1f5f1ec5b5b",
      "git_parent_sha": "d24dca3bbb50b1ebce7fdc835f3ce9bc53c3f466",
      "heuristic_id": "discrete-search-v1-local-search",
      "hypothesis": "Measure registered configuration using local-search at categorical distance 1 from the noise-qualified incumbent; improvement is unmeasured.",
      "incumbent_candidate": "seed8",
      "model_calls": 0,
      "neighborhood_radius": 1,
      "operator_version": "seed8-component-execution-v1",
      "parameters_before": {
        "checkpoint": true,
        "map_batch_size": null,
        "prevent_cse": false
      },
      "remaining_configurations": 12,
      "target_symbols": [
        "simulate._evaluate_component",
        "simulate.update"
      ]
    },
    "recipe": "discrete",
    "round_id": "round-001"
  },
  "proposal_id": "1480647fdf514cc7a7a47e78c11dbfbb",
  "provenance": {
    "acceptance": {
      "absolute_seconds": 0.02,
      "noise_guard": "maximum observed range of both candidates",
      "relative": 0.01
    },
    "context": {
      "bytes": 2528,
      "path": "contexts/94312dad4150a4daf58e4e678df02bba0ec10f70964d29def667396487ac6a4a.json",
      "sha256": "94312dad4150a4daf58e4e678df02bba0ec10f70964d29def667396487ac6a4a"
    },
    "context_sha256": "94312dad4150a4daf58e4e678df02bba0ec10f70964d29def667396487ac6a4a",
    "controller_commit": "5549b087ed6433a8af9a0cde4212e1f5f1ec5b5b",
    "git_parent_sha": "d24dca3bbb50b1ebce7fdc835f3ce9bc53c3f466",
    "heuristic_id": "discrete-search-v1-local-search",
    "hypothesis": "Measure registered configuration using local-search at categorical distance 1 from the noise-qualified incumbent; improvement is unmeasured.",
    "incumbent_candidate": "seed8",
    "model_calls": 0,
    "neighborhood_radius": 1,
    "operator_version": "seed8-component-execution-v1",
    "parameters_before": {
      "checkpoint": true,
      "map_batch_size": null,
      "prevent_cse": false
    },
    "remaining_configurations": 12,
    "target_symbols": [
      "simulate._evaluate_component",
      "simulate.update"
    ]
  },
  "recipe": "discrete",
  "response_sha256": null,
  "round_id": "round-001",
  "target_symbols": null,
  "uncertainty": "No repeat-confirmation or causality is inferred from this export. Inspect exact job evidence and matching cohorts.",
  "valid": true
}
```

## Decision and failure trail

| Sequence | Event | Actor | Detail |
| --- | --- | --- | --- |
| 1 | campaign_initialized | coordinator | {"spec_digest": "ab43e42f2273d104b7011a29517518470d89f87e9abd9d14ae35df3e3de42b7e"} |
| 2 | owner_claimed | coordinator | {"actor": "coordinator", "role": "coordinator", "version": 1} |
| 3 | round_created | coordinator | {"round_id": "round-001", "spec_digest": "c9eef3c088d8fc7635ca176417db487b5d2b4472ff28d94dfbae02855d9750d3", "version": 1} |
| 4 | candidate_proposed | coordinator | {"candidate_id": "seed8", "duplicate_of": null, "owner_version": 1, "proposal_digest": "747307f72d2353b16d682ecf026725777abbb10e43471431a2f48605b8058e78", "proposal_id": "seed8"} |
| 5 | evidence_observed | coordinator | {"candidate_id": "seed8", "category": "valid", "evidence_digest": "125d6c2c23633f90c332fa3335c1140be43ba921ee2fa03b888d3b7ec2e64d02", "evidence_id": "415bab6b82ef42baa0e0a5277df7aeb9:49937d87a08c533f73470c9dcc48dbc7870c12f467d9a8b5de192dffb5484afa", "job_id": "415bab6b82ef42baa0e0a5277df7aeb9", "progress": null, "status": "valid", "strikes": 0} |
| 6 | evidence_observed | coordinator | {"candidate_id": "seed8", "category": "valid", "evidence_digest": "b749c17cf48c04b1e780aeec1f0f2bf0a923112ea66497597c3c87831f15189b", "evidence_id": "882be0c143db470c9686cd2ba9e44c77:b547550f15337f868903dbcb118fa79d025993744270cf25cc8c7816a2e5616d", "job_id": "882be0c143db470c9686cd2ba9e44c77", "progress": null, "status": "valid", "strikes": 0} |
| 7 | evidence_observed | coordinator | {"candidate_id": "seed8", "category": "valid", "evidence_digest": "fd00ecb3420f8086341aa98abbea23f6ad20bbf19e7331993219037cb0324199", "evidence_id": "e6e5badb945c47ae927e511a3ff15fd7:820c7dfc19d0099d62f3b2315da0fb1dd7ee7ee9203b875447cfc2bd07d956a2", "job_id": "e6e5badb945c47ae927e511a3ff15fd7", "progress": null, "status": "valid", "strikes": 0} |
| 8 | candidate_proposed | coordinator | {"candidate_id": "import-42aaabf394d2d9bf5618b6802eb1e11315e85030", "duplicate_of": null, "owner_version": 1, "proposal_digest": "6ea031e07c01bdacd744c7f69c1d8f05dfa3134ce9238101b68c2c946991b8e2", "proposal_id": "import-42aaabf394d2d9bf5618b6802eb1e11315e85030"} |
| 9 | evidence_observed | coordinator | {"candidate_id": "import-42aaabf394d2d9bf5618b6802eb1e11315e85030", "category": "valid", "evidence_digest": "6d68b61ba47f578b3af5297deb6228177258c8d9cef86f6a7f09ed9c4c28dbdf", "evidence_id": "7f9a3863201d4908b9e2607e8b925bdc:70e1da46befd5d0fd365188a88a91391f95e2df62042e7a6687de8abbaf8c611", "job_id": "7f9a3863201d4908b9e2607e8b925bdc", "progress": null, "status": "valid", "strikes": 0} |
| 10 | decision_recorded | coordinator | {"decision_id": "c0610c553e8b44a3b99f037085e55c32", "payload": {"plan": {"action": "mutate", "attempted_parameters": [{"checkpoint": true, "map_batch_size": null, "prevent_cse": false}, {"checkpoint": true, "map_batch_size": null, "prevent_cse": true}], "base_candidate": "seed8", "dimensions": ["checkpoint", "prevent_cse", "map_batch_size"], "lane_id": "discrete", "owner": "coordinator", "parent_candidates": ["seed8", "import-42aaabf394d2d9bf5618b6802eb1e11315e85030"], "recipes": {"discrete": {"dimensions": ["checkpoint", "prevent_cse", "map_batch_size"]}}, "round_id": "round-001"}, "policy": "finite-space-local-search-v1"}, "payload_digest": "4533d134adc91c084d02baf48f95dedb33eff904270e7… [full detail in events.jsonl] |
| 11 | decision_recorded | coordinator | {"decision_id": "78273c30837743b594ef628e5c0056f2", "payload": {"acceptance": {"absolute_seconds": 0.02, "noise_guard": "maximum observed range of both candidates", "relative": 0.01}, "context": {"bytes": 2167, "path": "contexts/2092dd69a74463dcbb5e673c8548d722ee879145d57a12218f27a8d65070c13f.json", "sha256": "2092dd69a74463dcbb5e673c8548d722ee879145d57a12218f27a8d65070c13f"}, "heuristic_id": "discrete-search-v1-local-search", "hypothesis": "Measure registered configuration using local-search at categorical distance 1 from the noise-qualified incumbent; improvement is unmeasured.", "incumbent_candidate": "seed8", "neighborhood_radius": 1, "remaining_configurations": 13}, "payload_digest":… [full detail in events.jsonl] |
| 12 | candidate_proposed | coordinator | {"candidate_id": "78273c30837743b594ef628e5c0056f2", "duplicate_of": null, "owner_version": 1, "proposal_digest": "c3166c75215d7544270a05720d135af2c64eb20079f20242d4a082d3759bac0f", "proposal_id": "78273c30837743b594ef628e5c0056f2"} |
| 13 | evaluation_reserved | coordinator | {"attempt": 1, "candidate_id": "78273c30837743b594ef628e5c0056f2", "profile": "screen", "request_id": "1b702666abb64c298300b48af3e5bf4a"} |
| 14 | evaluation_bound | coordinator | {"job_id": "5b3af3628df54f778c117ffaad033a5e", "request_id": "1b702666abb64c298300b48af3e5bf4a"} |
| 15 | evidence_observed | coordinator | {"candidate_id": "78273c30837743b594ef628e5c0056f2", "category": "screen", "evidence_digest": "d8d1c0e80e2e742ca8434150a3b370f6b33fa4185692617476d2fb0895e49f9e", "evidence_id": "5b3af3628df54f778c117ffaad033a5e:34f77add4e58cd3f92f928160be72ce5d3350ed3868f51fb1e1c1a0fc5e1c9c9", "job_id": "5b3af3628df54f778c117ffaad033a5e", "progress": null, "status": "screened", "strikes": 0} |
| 16 | evaluation_reserved | coordinator | {"attempt": 1, "candidate_id": "78273c30837743b594ef628e5c0056f2", "profile": "full", "request_id": "4232037f6ce9412b8a1978d5f0126815"} |
| 17 | evaluation_bound | coordinator | {"job_id": "cde035e7126e4e00a4eccc5192f41d86", "request_id": "4232037f6ce9412b8a1978d5f0126815"} |
| 18 | evidence_observed | coordinator | {"candidate_id": "78273c30837743b594ef628e5c0056f2", "category": "valid", "evidence_digest": "4efb30e4052d596cf6aaf3be78f5694be6ae0e58348fa084b4ff8ed7077277c6", "evidence_id": "cde035e7126e4e00a4eccc5192f41d86:97a7e880e414101b6593ca85de16889e7fe6e0c28c1e57ad796fb9a0660824be", "job_id": "cde035e7126e4e00a4eccc5192f41d86", "progress": {"axes": ["compilation", "runtime", "peak_rss_bytes"], "meaningful_pareto": false, "meaningful_total": false, "policy": {"absolute": 0.02, "relative": 0.01}, "reference_best_total": 28.09352152608335, "reference_parents": ["seed8"]}, "status": "valid", "strikes": 1} |
| 19 | decision_recorded | coordinator | {"decision_id": "5e757aca8c5f41a49a913d1480f68a87", "payload": {"plan": {"action": "mutate", "attempted_parameters": [{"checkpoint": true, "map_batch_size": null, "prevent_cse": false}, {"checkpoint": true, "map_batch_size": null, "prevent_cse": true}, {"checkpoint": true, "map_batch_size": 1, "prevent_cse": false}], "base_candidate": "seed8", "dimensions": ["checkpoint", "prevent_cse", "map_batch_size"], "lane_id": "discrete", "owner": "coordinator", "parent_candidates": ["seed8", "import-42aaabf394d2d9bf5618b6802eb1e11315e85030", "78273c30837743b594ef628e5c0056f2"], "recipes": {"discrete": {"dimensions": ["checkpoint", "prevent_cse", "map_batch_size"]}}, "round_id": "round-001"}, "polic… [full detail in events.jsonl] |
| 20 | decision_recorded | coordinator | {"decision_id": "1480647fdf514cc7a7a47e78c11dbfbb", "payload": {"acceptance": {"absolute_seconds": 0.02, "noise_guard": "maximum observed range of both candidates", "relative": 0.01}, "context": {"bytes": 2528, "path": "contexts/94312dad4150a4daf58e4e678df02bba0ec10f70964d29def667396487ac6a4a.json", "sha256": "94312dad4150a4daf58e4e678df02bba0ec10f70964d29def667396487ac6a4a"}, "heuristic_id": "discrete-search-v1-local-search", "hypothesis": "Measure registered configuration using local-search at categorical distance 1 from the noise-qualified incumbent; improvement is unmeasured.", "incumbent_candidate": "seed8", "neighborhood_radius": 1, "remaining_configurations": 12}, "payload_digest":… [full detail in events.jsonl] |
| 21 | candidate_proposed | coordinator | {"candidate_id": "1480647fdf514cc7a7a47e78c11dbfbb", "duplicate_of": null, "owner_version": 1, "proposal_digest": "63bf57dadd9f593e32cc2627e8101eba8f1865cded7e31560b83c26904296ea6", "proposal_id": "1480647fdf514cc7a7a47e78c11dbfbb"} |
| 22 | evaluation_reserved | coordinator | {"attempt": 1, "candidate_id": "1480647fdf514cc7a7a47e78c11dbfbb", "profile": "screen", "request_id": "753a2cdb52ab484fb7826d23fd14ed93"} |
| 23 | evaluation_bound | coordinator | {"job_id": "f1c5134330144123bf6a90b7d712a544", "request_id": "753a2cdb52ab484fb7826d23fd14ed93"} |
| 24 | evidence_observed | coordinator | {"candidate_id": "1480647fdf514cc7a7a47e78c11dbfbb", "category": "screen", "evidence_digest": "05f8f5cdf504e68cc9ffaf6400067ee5ee6805ae4ddadcd4deea1d07870c99c0", "evidence_id": "f1c5134330144123bf6a90b7d712a544:663b207a2fd05652d225a8e39268e3768d8906f21c2b46fabb5257540816bac4", "job_id": "f1c5134330144123bf6a90b7d712a544", "progress": null, "status": "screened", "strikes": 1} |
| 25 | evaluation_reserved | coordinator | {"attempt": 1, "candidate_id": "1480647fdf514cc7a7a47e78c11dbfbb", "profile": "full", "request_id": "faff7d74001d46d38ed0ea288e4ac0ac"} |
| 26 | evaluation_bound | coordinator | {"job_id": "8d433ae433e5496b89cb4de587c0862f", "request_id": "faff7d74001d46d38ed0ea288e4ac0ac"} |
| 27 | evidence_observed | coordinator | {"candidate_id": "1480647fdf514cc7a7a47e78c11dbfbb", "category": "valid", "evidence_digest": "becce5c3e245e12424f0b8b8c996884ca6f3c16fdb24c8543e85c809dd26237d", "evidence_id": "8d433ae433e5496b89cb4de587c0862f:e73ec4d8e0e0b141c91c65a03e7de4e446cb51042c5f42264060bcc887a94bbf", "job_id": "8d433ae433e5496b89cb4de587c0862f", "progress": {"axes": ["compilation", "runtime", "peak_rss_bytes"], "meaningful_pareto": false, "meaningful_total": false, "policy": {"absolute": 0.02, "relative": 0.01}, "reference_best_total": 28.09352152608335, "reference_parents": ["seed8"]}, "status": "valid", "strikes": 2} |

Guidance may propose a new round. It cannot silently replace frozen operators, ownership, evaluation requirements or budgets. Only the coordinator can admit that round through the campaign state API. Publishing this ledger does not merge or promote candidate code.
