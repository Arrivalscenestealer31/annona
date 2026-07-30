# Deploying Annona

Three ways to run it, in order of how much hardware you have. The kernel is the
same image and the same policy schema in all three — what changes is which
substrates the policy registers.

---

## 1. On a laptop, in a minute

```bash
docker compose up -d
docker compose exec annona-ollama ollama pull qwen2.5:14b
docker compose exec annona annona policy init --endpoint http://ollama:11434 --model qwen2.5:14b
docker compose exec annona annona substrates
```

That is a working appliance: a kernel, a local model, a policy that registers
nothing off the machine, and a ledger on a volume. Nothing can leave, because
nothing outside is declared.

## 2. On a DGX Spark or any GPU server

The DGX Spark is **arm64** with CUDA 13. Two consequences that cost an afternoon
if you find them on site:

- every image must be `linux/arm64`. `make image-multiarch` builds both
  architectures; an amd64-only image does not run on a GB10, and the failure is
  not obvious.
- NVIDIA NIM containers need the `-dgx-spark` variants. vLLM, llama.cpp and
  Ollama all have working arm64 builds.

```bash
# vLLM instead of Ollama — the appliance profile
VLLM_MODEL=Qwen/Qwen2.5-14B-Instruct-AWQ docker compose --profile vllm up -d

# register it, then check that the kernel can see it
docker compose exec annona annona policy init \
    --endpoint http://vllm:8000/v1 --model local
docker compose exec annona annona substrates
```

Edit `~/.annona/policy.yaml` on the volume to set `kind: openai-compatible` for
that substrate — vLLM speaks `/v1`, not Ollama's native API.

**Sizing, from the hardware rather than the datasheet.** A GB10 has 128 GB of
unified memory and about 273 GB/s of bandwidth. Capacity is generous; bandwidth
is the ceiling, and token generation is bandwidth-bound. A 14B model at Q4 is
the sweet spot for interactive use; a 32B at Q4 fits and is materially slower.
Plan concurrency, not parameter count.

**One box is one failure domain.** The appliance profile is not highly
available. If that matters, run two boxes over the 200 GbE link, or declare a
second substrate in the policy for the classes that are allowed to use it — and
say out loud that restricted work will be *held* during an outage, because that
is what it will do.

## 3. In your own cloud tenant

Same image, same compose file, a policy that registers your GPU cluster instead
of a local runtime. The only thing that changes is `jurisdiction` and
`max_class` on each substrate, which is the whole point of the design.

---

## Verifying an appliance before you hand it over

```bash
make verify                                    # against a local Ollama
python deploy/verify_appliance.py \
    --kind openai-compatible \
    --endpoint http://vllm:8000/v1 --model local
```

Nine checks, ten seconds, exit code 0 or 1. It plants a canary in a client file,
lets a real agent read it, and then asserts the things a customer's auditor
would test:

```
  pass  the local runtime answers
  pass  the model called the tool
  pass  reading a client file made the run restricted
  pass  no payload reached the frontier substrate
  pass  leak rate is zero
  pass  every inference was placed on-prem
  pass  the ledger chain verifies
  pass  the run produced an answer
  pass  with the GPU down, restricted work is held (not rerouted)
```

The last one is the commercial test. Everything else on the market passes the
other eight.

---

## What the deployment gives you, and what it does not

**It gives you.** An unprivileged daemon that never touches the GPU; a model
server that never touches your data; a policy and a ledger on volumes you back
up; no inbound port (the UI is bound to loopback on the host, reach it over your
own tunnel); signed, digest-pinned images.

**It does not give you** confidential computing. Encrypted memory and GPU remote
attestation are real on HGX B200-class hardware and are **not available on a
GB10**. A privileged host administrator can read process memory. On-prem, that
administrator is the customer — the threat model here is the vendor and the
network, not the owner of the machine — but it should be said in the room rather
than discovered in an audit.

---

## Operating it

```bash
annona substrates          # what is registered, where it is, whether it is up
annona policy show         # the policy as the runtime understands it
annona policy test restricted --probe   # where would restricted work go, right now?
annona audit --held        # every refusal, with the reason
annona verify              # check the ledger chain, offline
annona why step_7f3a       # reconstruct one decision
```

`annona policy test` is the one to run before a change goes live rather than
after an incident: it answers "if this were restricted, where would it go?"
without needing restricted material to try it with.

## Upgrading

Volumes hold the policy, the ledger and the vault; the image holds none of them.

```bash
docker compose pull && docker compose up -d
docker compose exec annona annona verify     # the chain continues across the upgrade
```
