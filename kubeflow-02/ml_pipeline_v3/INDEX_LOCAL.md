# 📚 Local Pipeline Execution - Documentation Index

Complete guide to running the FLTS Kubeflow Pipeline locally without Docker, Kubernetes, or Kubeflow.

---

## 🚀 Start Here

### For First-Time Users

1. **[README_LOCAL.md](README_LOCAL.md)** - **START HERE**
   - Quick 30-second start
   - Basic usage examples
   - Output structure overview
   - Quick troubleshooting

### For Detailed Information

2. **[LOCAL_EXECUTION_GUIDE.md](LOCAL_EXECUTION_GUIDE.md)** - **DEEP DIVE**
   - Complete prerequisites
   - Step-by-step walkthrough
   - All configuration options
   - Advanced usage patterns
   - Comprehensive troubleshooting

### For Visual Learners

3. **[LOCAL_EXECUTION_VISUAL_GUIDE.md](LOCAL_EXECUTION_VISUAL_GUIDE.md)** - **DIAGRAMS**
   - Architecture comparisons
   - Execution flow diagrams
   - Data flow visualization
   - Component mapping
   - Performance comparisons

### Setup Summary

4. **[LOCAL_SETUP_SUMMARY.md](LOCAL_SETUP_SUMMARY.md)** - **WHAT WAS CREATED**
   - Files created overview
   - How to use each file
   - Key features summary
   - Requirements checklist

---

## 📁 Files Overview

### Executable Files

| File | Purpose | How to Use |
|------|---------|------------|
| **quickstart_local.sh** | One-command launcher | `./quickstart_local.sh` |
| **run_pipeline_locally.py** | Main execution script | `python run_pipeline_locally.py` |

### Documentation Files

| File | Audience | Content |
|------|----------|---------|
| **README_LOCAL.md** | Everyone | Quick reference, 30-sec start |
| **LOCAL_EXECUTION_GUIDE.md** | Developers | Complete guide, all details |
| **LOCAL_EXECUTION_VISUAL_GUIDE.md** | Visual learners | Diagrams and flows |
| **LOCAL_SETUP_SUMMARY.md** | Setup reviewers | What was created |
| **INDEX_LOCAL.md** (this file) | Navigation | Documentation index |

---

## 🎯 Use Case → Documentation

### "I just want to run it"
→ **[README_LOCAL.md](README_LOCAL.md)** → Quick Start section

### "I need to understand what it does"
→ **[LOCAL_EXECUTION_VISUAL_GUIDE.md](LOCAL_EXECUTION_VISUAL_GUIDE.md)** → Execution Flow Diagram

### "I want to customize parameters"
→ **[LOCAL_EXECUTION_GUIDE.md](LOCAL_EXECUTION_GUIDE.md)** → Configuration section

### "Something went wrong"
→ **[LOCAL_EXECUTION_GUIDE.md](LOCAL_EXECUTION_GUIDE.md)** → Troubleshooting section

### "How does this compare to KFP?"
→ **[LOCAL_EXECUTION_VISUAL_GUIDE.md](LOCAL_EXECUTION_VISUAL_GUIDE.md)** → Architecture Comparison

### "I want to modify the pipeline"
→ **[LOCAL_EXECUTION_GUIDE.md](LOCAL_EXECUTION_GUIDE.md)** → Development Workflow section

---

## 📖 Reading Order by Experience Level

### Beginner (Never used the pipeline)

1. **README_LOCAL.md** - Quick Start
2. Run: `./quickstart_local.sh`
3. **LOCAL_EXECUTION_VISUAL_GUIDE.md** - Understand what happened
4. **LOCAL_EXECUTION_GUIDE.md** - Learn customization

### Intermediate (Familiar with ML pipelines)

1. **LOCAL_EXECUTION_VISUAL_GUIDE.md** - Architecture overview
2. **README_LOCAL.md** - Usage patterns
3. Run: `python run_pipeline_locally.py --help`
4. **LOCAL_EXECUTION_GUIDE.md** - Advanced usage

### Advanced (Want to modify pipeline)

1. **LOCAL_SETUP_SUMMARY.md** - Implementation details
2. **run_pipeline_locally.py** - Source code
3. **LOCAL_EXECUTION_GUIDE.md** - Development workflow
4. **kubeflow_pipeline/README.md** - KFP v2 pipeline definition

---

## 🔗 Related Documentation

### Kubeflow Pipeline Definition (KFP v2)

- **[kubeflow_pipeline/README.md](kubeflow_pipeline/README.md)** - Pipeline definition and compilation (Steps 0-8)
- **[kubeflow_pipeline/components_v2.py](kubeflow_pipeline/components_v2.py)** - Component definitions
- **[kubeflow_pipeline/pipeline_v2.py](kubeflow_pipeline/pipeline_v2.py)** - Pipeline DAG

### Deployment Documentation

- **[STEP_9_VERIFICATION.md](STEP_9_VERIFICATION.md)** - Kubeflow deployment (not covered in local execution)
- **[FINAL_REPORT_KFP_V2_MIGRATION.md](FINAL_REPORT_KFP_V2_MIGRATION.md)** - KFP v1→v2 migration details

---

## 🗺️ Documentation Map

```
Local Execution Documentation
│
├── README_LOCAL.md                    ← START: Quick reference
│   ├── Quick Start (30 seconds)
│   ├── Usage Options
│   └── Output Structure
│
├── LOCAL_EXECUTION_GUIDE.md           ← DEEP DIVE: Complete guide
│   ├── Prerequisites
│   ├── Quick Start
│   ├── Pipeline Steps (detailed)
│   ├── Configuration
│   ├── Output Artifacts
│   ├── Troubleshooting
│   └── Advanced Usage
│
├── LOCAL_EXECUTION_VISUAL_GUIDE.md    ← DIAGRAMS: Visual guide
│   ├── Architecture Comparison
│   ├── Execution Flow Diagram
│   ├── Data Flow
│   ├── Component Mapping
│   └── Performance Comparison
│
├── LOCAL_SETUP_SUMMARY.md             ← SUMMARY: What was created
│   ├── Files Created
│   ├── How to Use
│   └── Key Features
│
└── INDEX_LOCAL.md (this file)         ← NAVIGATION: Documentation index
    ├── Start Here
    ├── Files Overview
    └── Use Case Guide
```

---

## ⚡ Quick Commands

```bash
# View documentation
cat README_LOCAL.md                    # Quick reference
cat LOCAL_EXECUTION_GUIDE.md           # Complete guide
cat LOCAL_EXECUTION_VISUAL_GUIDE.md    # Visual diagrams
cat LOCAL_SETUP_SUMMARY.md             # Setup summary

# Run pipeline
./quickstart_local.sh                  # Quick start (default dataset)
./quickstart_local.sh ElBorn           # Custom dataset
python run_pipeline_locally.py --help  # See all options

# View results
cat local_artifacts/*/evaluations/evaluation_results.json | jq .
head local_artifacts/*/predictions/predictions.csv
```

---

## 📊 Feature Comparison Table

| Feature | README_LOCAL | EXECUTION_GUIDE | VISUAL_GUIDE | SETUP_SUMMARY |
|---------|--------------|-----------------|--------------|---------------|
| Quick Start | ✅ Primary | ✅ Detailed | ❌ | ✅ Brief |
| Prerequisites | ⚠️ Brief | ✅ Complete | ❌ | ✅ Summary |
| Step-by-step | ⚠️ Overview | ✅ Detailed | ✅ Diagrams | ❌ |
| Configuration | ⚠️ Basic | ✅ Complete | ❌ | ❌ |
| Troubleshooting | ⚠️ Common | ✅ Comprehensive | ❌ | ⚠️ Links |
| Architecture | ⚠️ Table | ⚠️ Text | ✅ Diagrams | ⚠️ Brief |
| Advanced Usage | ❌ | ✅ Extensive | ❌ | ❌ |
| Examples | ✅ Session | ✅ Multiple | ✅ Commands | ✅ Use Cases |

**Legend:** ✅ Comprehensive | ⚠️ Partial | ❌ Not Covered

---

## 🎓 Learning Path

### Path 1: Quick Execution (15 minutes)

1. Read **README_LOCAL.md** (3 min)
2. Run `./quickstart_local.sh` (3 min)
3. Inspect results (5 min)
4. Skim **LOCAL_EXECUTION_VISUAL_GUIDE.md** (4 min)

### Path 2: Understanding Pipeline (45 minutes)

1. Read **LOCAL_EXECUTION_VISUAL_GUIDE.md** (10 min)
2. Read **LOCAL_EXECUTION_GUIDE.md** - Pipeline Steps (15 min)
3. Run pipeline with custom options (10 min)
4. Review **kubeflow_pipeline/README.md** (10 min)

### Path 3: Advanced Development (2 hours)

1. Study **run_pipeline_locally.py** source code (30 min)
2. Read **LOCAL_EXECUTION_GUIDE.md** - Complete (30 min)
3. Modify hyperparameters and re-run (30 min)
4. Compare with KFP pipeline definition (30 min)

---

## 💡 Tips for Finding Information

### "How do I...?"

| Question | Document | Section |
|----------|----------|---------|
| Run the pipeline? | README_LOCAL.md | Quick Start |
| Install dependencies? | LOCAL_EXECUTION_GUIDE.md | Prerequisites |
| Change dataset? | README_LOCAL.md | Usage Options |
| Tune hyperparameters? | LOCAL_EXECUTION_GUIDE.md | Configuration |
| Fix errors? | LOCAL_EXECUTION_GUIDE.md | Troubleshooting |
| Understand flow? | LOCAL_EXECUTION_VISUAL_GUIDE.md | Execution Flow |
| Compare to KFP? | LOCAL_EXECUTION_VISUAL_GUIDE.md | Architecture Comparison |
| View results? | README_LOCAL.md | View Results |
| Modify pipeline? | LOCAL_EXECUTION_GUIDE.md | Development Workflow |

---

## 🔍 Search Tips

### Finding Specific Information

```bash
# Search across all documentation
grep -r "your search term" *LOCAL*.md

# Find configuration options
grep -A 10 "Configuration" LOCAL_EXECUTION_GUIDE.md

# Find error solutions
grep -A 5 "Error:" LOCAL_EXECUTION_GUIDE.md

# Find commands
grep "^\`\`\`bash" LOCAL_EXECUTION_GUIDE.md -A 3
```

---

## 📞 Getting Help

### Troubleshooting Hierarchy

1. **Check Terminal Output** - Error messages are descriptive
2. **README_LOCAL.md** - Common issues section
3. **LOCAL_EXECUTION_GUIDE.md** - Comprehensive troubleshooting
4. **Source Code** - `run_pipeline_locally.py` has inline comments

### Common Issues Quick Links

- **Missing Dependencies** → [LOCAL_EXECUTION_GUIDE.md#issue-missing-dependencies](LOCAL_EXECUTION_GUIDE.md#issue-missing-dependencies)
- **Dataset Not Found** → [LOCAL_EXECUTION_GUIDE.md#issue-dataset-not-found](LOCAL_EXECUTION_GUIDE.md#issue-dataset-not-found)
- **Python Version** → [LOCAL_EXECUTION_GUIDE.md#issue-python-version](LOCAL_EXECUTION_GUIDE.md#issue-python-version)
- **Out of Memory** → [LOCAL_EXECUTION_GUIDE.md#issue-out-of-memory](LOCAL_EXECUTION_GUIDE.md#issue-out-of-memory)

---

## 📝 Documentation Standards

All local execution documentation follows these conventions:

- **Headers:** Clear, action-oriented
- **Code blocks:** Syntax-highlighted with language tags
- **Examples:** Realistic, runnable commands
- **Status indicators:** ✅ (done), ⚠️ (partial), ❌ (not done)
- **File paths:** Absolute paths when needed
- **Commands:** Copy-paste ready

---

## 🎯 Next Actions

### Immediate (Now)

1. Read **[README_LOCAL.md](README_LOCAL.md)**
2. Run `./quickstart_local.sh`
3. Inspect `local_artifacts/` directory

### Short-term (This Session)

1. Review **[LOCAL_EXECUTION_VISUAL_GUIDE.md](LOCAL_EXECUTION_VISUAL_GUIDE.md)**
2. Try different datasets (PobleSec, ElBorn, LesCorts)
3. Compare model performances

### Long-term (Next Steps)

1. Study **[LOCAL_EXECUTION_GUIDE.md](LOCAL_EXECUTION_GUIDE.md)** completely
2. Modify hyperparameters in `run_pipeline_locally.py`
3. Proceed to KFP deployment (Step 9)

---

## ✅ Checklist

Before running the pipeline, ensure:

- [ ] Python 3.11+ installed
- [ ] Located in `ml_pipeline_v3/` directory
- [ ] Dataset file exists (`ls dataset/PobleSec.csv`)
- [ ] Read **README_LOCAL.md**
- [ ] Virtual environment activated (optional but recommended)

After running:

- [ ] Check `local_artifacts/{identifier}/` created
- [ ] Verify all 5 subdirectories have files
- [ ] Review evaluation results
- [ ] Inspect predictions CSV

---

## 📚 Complete File List

### Created for Local Execution

```
ml_pipeline_v3/
├── run_pipeline_locally.py              ← Main script
├── quickstart_local.sh                  ← Quick launcher
├── README_LOCAL.md                      ← Quick reference
├── LOCAL_EXECUTION_GUIDE.md             ← Complete guide
├── LOCAL_EXECUTION_VISUAL_GUIDE.md      ← Visual diagrams
├── LOCAL_SETUP_SUMMARY.md               ← Setup summary
└── INDEX_LOCAL.md                       ← This file
```

### Supporting Documentation

```
ml_pipeline_v3/
├── kubeflow_pipeline/
│   ├── README.md                        ← KFP pipeline (Steps 0-8)
│   ├── components_v2.py                 ← Component definitions
│   └── pipeline_v2.py                   ← Pipeline DAG
├── FINAL_REPORT_KFP_V2_MIGRATION.md     ← Migration report
└── STEP_9_VERIFICATION.md               ← Deployment guide
```

---

## 🚀 Ready to Start?

```bash
cd ml_pipeline_v3
cat README_LOCAL.md          # Read quick reference (2 min)
./quickstart_local.sh        # Run pipeline (3 min)
# Enjoy your results! 🎉
```

---

**Documentation Index Version:** 1.0  
**Last Updated:** Based on KFP v2 pipeline definition  
**Maintained By:** Auto-generated from `kubeflow_pipeline/README.md`
