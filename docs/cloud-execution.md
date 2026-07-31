# Using your machine as a cloud app's executor

A web app you use in the browser can run its steps here instead of on its
vendor's servers. The request never reaches them: the page calls the daemon on
`127.0.0.1`, your policy decides which substrate may serve the turn, and the
answer comes back with the placement attached.

This page is about turning that on safely, because the daemon's neighbours are
not other computers — they are the other tabs in your browser.

## The rule

**Same origin is trusted. Everything else pairs.**

The window Annona ships with talks to the daemon from a local origin and needs
no credential; that is unchanged. Any other origin must be *listed* **and**
present a token you copied off this machine. Listed without a token is refused.
A valid token from an unlisted origin is refused. Both matter: the first stops a
page that guessed the port, the second stops a leaked token turning every site
into an executor.

## Pairing

```console
$ annona pair

🔗 Paired. Paste this token into the app's local-execution setting:

   xJ2f…                                   ← the token

   allowed origins  https://app.akaion.com
   stored in        ~/.annona/pairing.json (mode 600)
```

Then, in the app: **Settings → Privacy → Execution on your machine**, paste the
token, and switch it on. From then on the model picker offers **Annona (locale)**
and every answer carries where it ran.

Other origins, and revocation:

```console
$ annona pair -o https://studio.example -o https://app.akaion.com
$ annona pair --show      # the current token, without minting a new one
$ annona pair --revoke    # every web app has to pair again
```

There is no recovery, only a new token. Rotating is `annona pair` again.

## What the app can and cannot do

Paired, an app may read the perimeter and run requests through it:

| | |
|---|---|
| `GET /api/kernel/status` | is a policy enforcing, how many substrates and rules |
| `GET /api/kernel/policy` | the policy as the runtime understands it |
| `GET /api/kernel/substrates` | what is registered and whether it answers |
| `GET /api/kernel/ledger` | recent decisions, refusals included |
| `GET /api/kernel/ledger/verify` | the chain, checked offline |
| `POST /api/kernel/ask` | run one request through the perimeter |

It cannot change the policy. Editing the perimeter from a page is a larger
decision than reading it, and this is not that decision. Change the policy on the
machine, with a file and a text editor.

`/health` stays open without a token, deliberately: an app has to be able to say
"Annona is running here, pair with it" before anyone has pasted anything.

## Why Chrome asks first

A request from a public page to `127.0.0.1` is a Private Network Access request.
Chrome sends a preflight carrying `Access-Control-Request-Private-Network` and
will not proceed unless the response says
`Access-Control-Allow-Private-Network: true`.

Annona answers that header **only for listed origins**. It is a statement that
this daemon knowingly accepts calls from a public page, and saying it to an
origin you have not listed would be saying it to anyone.

If the app reports the daemon as unreachable while `annona status` says it is
running, this is usually why — an older build, or an origin that is not on the
list.

## What this does not give you

- **The page still sees the answer.** Execution is local; the browser tab
  rendering the result belongs to the app's vendor, and whatever the page does
  with what it received is between you and them. Annona controls where the work
  happened, not what a page does afterwards.
- **A token is not a user.** Anyone holding it can run steps on this machine from
  a listed origin — including another profile in the same browser. It is stored
  `0600` and it is not shared between machines.
- **Loopback is the boundary.** The daemon binds `127.0.0.1` unless `ANNONA_BIND`
  says otherwise (the container image sets it). Pairing does not open a port to
  your network; it decides who, on this machine, may use the one already open.
