# Objective-mode conditioned selector

| design | mode | safe candidates | mode oracle | LLM choice | mode acc | gate | cond. regret |
|---|---|---|---|---|---|---|---|
| aes | balanced | density_040,grt_200,pad_2 | pad_2 | - | - | - | - |
| aes | timing_first | density_040,grt_200,pad_2 | pad_2 | - | - | - | - |
| aes | HPWL_first | density_040,grt_200,pad_2 | pad_2 | - | - | - | - |
| aes | power_first | density_040,grt_200,pad_2 | pad_2 | - | - | - | - |
| gcd | balanced | density_025,density_035,density_040,grt_200,layeradj,pad_2 | density_025 | - | - | - | - |
| gcd | timing_first | density_025,density_035,density_040,grt_200,layeradj,pad_2 | density_025 | - | - | - | - |
| gcd | HPWL_first | density_025,density_035,density_040,grt_200,layeradj,pad_2 | pad_2 | - | - | - | - |
| gcd | power_first | density_025,density_035,density_040,grt_200,layeradj,pad_2 | density_035 | - | - | - | - |
| ibex | balanced | pad_2 | pad_2 | - | - | - | - |
| ibex | timing_first | pad_2 | pad_2 | - | - | - | - |
| ibex | HPWL_first | pad_2 | pad_2 | - | - | - | - |
| ibex | power_first | pad_2 | pad_2 | - | - | - | - |
| jpeg | balanced | layeradj | layeradj | - | - | - | - |
| jpeg | timing_first | layeradj | layeradj | - | - | - | - |
| jpeg | HPWL_first | layeradj | layeradj | - | - | - | - |
| jpeg | power_first | layeradj | layeradj | - | - | - | - |

Mode weights (d_HPWL, d_TNS, d_power): {"balanced": [0.5, 0.4, 0.1], "timing_first": [0.1, 0.8, 0.1], "HPWL_first": [0.8, 0.1, 0.1], "power_first": [0.1, 0.1, 0.8]}
WNS is a hard gate (setup and hold separately, guard 0.02 ns); not a soft objective.
