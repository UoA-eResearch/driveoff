# driveoff-web

Frontend service for drive offboarding. Built with Vue.

## Generate API client
This project uses heyapi to generate client code and TypeScript types based on OpenAPI specification that's produced by Pydantic/FastAPI. When models and endpoints change, the client code needs to be regenerated. To do this:
1. Run the fastapi server. `fastapi dev src/api/main.py`
2. In the `web/` directory, run `npm run openapi-ts`. It will retrieve the OpenAPI specification from FastAPI server running on localhost, generate API client code and types, and place them in `web/src/client`.
3. Add and commit the generated code. 

Do not manually edit code in `web/src/client`, they will be overwritten next time the types are regenerated.


## Recommended IDE Setup

[VSCode](https://code.visualstudio.com/) + [Volar](https://marketplace.visualstudio.com/items?itemName=Vue.volar) (and disable Vetur).

## Type Support for `.vue` Imports in TS

TypeScript cannot handle type information for `.vue` imports by default, so we replace the `tsc` CLI with `vue-tsc` for type checking. In editors, we need [Volar](https://marketplace.visualstudio.com/items?itemName=Vue.volar) to make the TypeScript language service aware of `.vue` types.

## Customize configuration

See [Vite Configuration Reference](https://vitejs.dev/config/).

## Project Setup

```sh
npm install
```

### Compile and Hot-Reload for Development

```sh
npm run dev
```

### Type-Check, Compile and Minify for Production

```sh
npm run build
```

### Run Unit Tests with [Vitest](https://vitest.dev/)

```sh
npm run test:unit
```

### Lint with [ESLint](https://eslint.org/)

```sh
npm run lint
```
