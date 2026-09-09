# Schémas techniques ASCII

Quand la question porte sur un ouvrage technique et que les documents du projet contiennent les dimensions, illustre ta réponse avec le schéma ASCII correspondant en remplaçant les valeurs par celles du projet. Si une valeur est absente des documents, indique "?".

---

## Semelle filante (coupe transversale)

```
                    ┌─────────┐
                    │         │
                    │   MUR   │
                    │  a=__cm │
                    │         │
         ┌──────────┴─────────┴──────────┐
         │                               │
         │        SEMELLE  B=__cm        │
         │          H=__cm               │
         ├───────────────────────────────┤
         │        GROS BÉTON __cm        │
─────────┴───────────────────────────────┴───────── Fond de fouille
```

## Semelle isolée (coupe transversale)

```
                    ┌─────────┐
                    │ POTEAU  │
                    │ __x__cm │
                    │         │
         ┌──────────┴─────────┴──────────┐
         │                               │
         │     SEMELLE ISOLÉE __x__cm    │
         │          H=__cm               │
         ├───────────────────────────────┤
         │        GROS BÉTON __cm        │
─────────┴───────────────────────────────┴───────── Fond de fouille
```

## Dallage sur terre-plein (coupe)

```
─────────────────────────────────────────────── Sol fini
         ┌───────────────────────────────┐
         │       REVÊTEMENT __cm         │
         ├───────────────────────────────┤
         │         CHAPE __cm            │
         ├───────────────────────────────┤
         │                               │
         │       ISOLANT PSE __cm        │
         │                               │
         ├───────────────────────────────┤
         │        DALLAGE BA __cm        │
         ├───────────────────────────────┤
         │     FORME EN GRAVIER __cm     │
─────────┴───────────────────────────────┴───────── Plateforme
```

## Mur avec doublage intérieur (coupe horizontale)

```
EXT                                          INT
  │                                           │
  │  ENDUIT  ┌───────────┬──────┬───────────┐
  │  __cm    │  MUR __cm │ISO   │ PLAQUE    │
  │          │           │__cm  │ __mm      │
  │          │           │      │           │
  │          └───────────┴──────┴───────────┘
  │                                           │
```

## Plancher hourdis (coupe transversale)

```
─────────────────────────────────────────────── Sol fini
         ┌───────────────────────────────┐
         │       REVÊTEMENT __cm         │
         ├───────────────────────────────┤
         │         CHAPE __cm            │
         ├───────────────────────────────┤
         │       ISOLANT __cm            │
         ├──────┬────────────────┬───────┤
         │HOURD.│   POUTRELLE    │HOURD. │
         │__cm  │    __cm        │__cm   │
         ├──────┴────────────────┴───────┤
         │     DALLE COMPRESSION __cm    │
─────────┴───────────────────────────────┴───────── Sous-face
```

## Toiture terrasse (coupe)

```
─────────────────────────────────────────────── Protection __
         ┌───────────────────────────────┐
         │     ÉTANCHÉITÉ __mm           │
         ├───────────────────────────────┤
         │                               │
         │     ISOLANT __cm              │
         │                               │
         ├───────────────────────────────┤
         │     PARE-VAPEUR               │
         ├───────────────────────────────┤
         │     FORME DE PENTE __cm       │
         ├───────────────────────────────┤
         │     DALLE BA __cm             │
─────────┴───────────────────────────────┴───────── Sous-face
```

## Charpente + couverture (coupe simplifiée)

```
                    /\
                   /  \
                  / __cm\        ← COUVERTURE (tuiles/ardoises)
                 /──────\
                / LITEAUX \
               /───────────\
              /  ÉCRAN S/T  \
             /───────────────\
            /   CHEVRONS __cm \
           /─────────────────────\
          /    ISOLANT __cm       \
         /─────────────────────────\
        /      PARE-VAPEUR          \
       /─────────────────────────────\
──────/        PLAQUE __mm            \────────
      ├───────────────────────────────┤
                 PANNE
```
