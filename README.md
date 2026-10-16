<div align="center">

<img src="frontend/public/icons/icon-192.png" width="96" alt="Logotipo de Kcalia" />

# Kcalia

**Calorías y macros, con calma.**
Cuenta lo que comes con una frase, una foto, un audio o el código de barras. Lo que repites se recuerda, así que casi nunca hace falta volver a preguntar a la IA.

[![CI](https://github.com/Alvaro-Rovira/kcalia/actions/workflows/ci.yml/badge.svg)](https://github.com/Alvaro-Rovira/kcalia/actions/workflows/ci.yml)
[![Licencia MIT](https://img.shields.io/badge/licencia-MIT-34d399.svg)](LICENSE)
![PWA](https://img.shields.io/badge/PWA-instalable-7f95ff.svg)
![Python 3.12](https://img.shields.io/badge/Python-3.12-3776ab.svg?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688.svg?logo=fastapi&logoColor=white)
![React 19](https://img.shields.io/badge/React-19-61dafb.svg?logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-3178c6.svg?logo=typescript&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ed.svg?logo=docker&logoColor=white)

<picture>
  <source media="(prefers-color-scheme: light)" srcset="docs/hero-light.png" />
  <img src="docs/hero-dark.png" alt="Cuatro pantallas de Kcalia: el día de hoy con el anillo de calorías, la revisión de una comida analizada, el historial con las calorías de cada día y las rutinas de entreno" />
</picture>

</div>

Kcalia es una PWA en español, pensada primero para el móvil, que vive en tu propio servidor. La instalación de referencia está en **[kcalia.space](https://kcalia.space)**. Se instala en el iPhone o en Android como una app más, funciona sin conexión para lo que ya conoce y tus datos no salen de tu máquina. Es para ti y para las personas a las que tú des acceso: cada cuenta nueva espera tu aprobación y cada una ve solo lo suyo.

<div align="center">
<img src="docs/demo.gif" width="270" alt="Animación: se escribe «bocadillo de jamón serrano con tomate y aceite», la IA devuelve el desglose, se sube la ración a ×1,5 y se guarda" />
<img src="docs/demo-etiqueta.gif" width="250" alt="Animación: se fotografía la etiqueta de unas galletas, la app la lee, se guarda y «tres galletas integrales» se calcula con esas cifras sin consultar a la IA" />
<img src="docs/demo-entreno.gif" width="250" alt="Animación: se empieza la rutina de pierna, se apunta una serie de sentadilla, corre el descanso, se repite la serie y se termina el entreno" />
</div>

## Índice

- [Características](#características)
- [Capturas](#capturas)
- [Cómo se calculan las calorías](#cómo-se-calculan-las-calorías)
- [Cómo se ahorra IA](#cómo-se-ahorra-ia)
- [Cómo se calculan los objetivos](#cómo-se-calculan-los-objetivos)
- [Arquitectura](#arquitectura)
- [Seguridad y privacidad](#seguridad-y-privacidad)
- [Stack](#stack)
- [Puesta en marcha con Docker](#puesta-en-marcha-con-docker)
- [Variables de entorno](#variables-de-entorno)
- [Despliegue en una VPS](#despliegue-en-una-vps)
- [Cuentas y administración](#cuentas-y-administración)
- [Migrar a un dominio propio](#migrar-a-un-dominio-propio)
- [Instalar la app en el móvil](#instalar-la-app-en-el-móvil)
- [Elegir el modelo de IA](#elegir-el-modelo-de-ia)
- [Copias de seguridad](#copias-de-seguridad)
- [Desarrollo y pruebas](#desarrollo-y-pruebas)
- [Pendiente](#pendiente)
- [Roadmap](#roadmap)
- [Licencia](#licencia)

## Características

**Registrar lo que comes**

- **Texto libre.** «Dos huevos revueltos con una tostada de pan integral y aceite» se convierte en ingredientes con gramos, calorías, proteínas, hidratos, grasas y fibra. Antes de guardar ves el desglose y puedes corregir cualquier cantidad o añadir un ingrediente a mano (con autocompletado de los que ya conoce y de la tabla oficial de alimentos).
- **Valores oficiales, no inventados.** Las calorías y los macros de cada alimento salen de una tabla oficial (CIQUAL 2025 y USDA, 472 alimentos habituales en España y 22 platos por receta); la IA solo dice qué hay en el plato y cuánto. Cada ingrediente indica si su valor es oficial, de una etiqueta, tuyo o estimado, y cada comida muestra qué parte de sus calorías es oficial. Más en [Cómo se calculan las calorías](#cómo-se-calculan-las-calorías).
- **Foto, sola o con tu descripción.** Adjuntas la foto (se reduce en el móvil) y, antes o después, escribes o dictas lo que no se ve: «debajo había dos cucharadas de aceite», «era media ración». La IA de visión recibe las dos cosas en una sola consulta; la foto marca el tamaño de las raciones y tu descripción manda en lo que no se ve o no cuadra. La comida queda guardada con tu texto, así que la próxima vez que lo escribas igual sale del historial sin IA.
- **Voz.** Grabas, se transcribe con un Whisper propio que corre en tu servidor (unos 4-5 segundos por frase en CPU) y el texto aparece en el cuadro para que lo revises, le añadas una foto si quieres y lo envíes. En el iPhone, además, un atajo de Siri: «Oye Siri, apuntar en Kcalia».
- **Código de barras.** Se escanea con la cámara (con el detector nativo del navegador o, en iPhone, un lector WebAssembly que se descarga solo la primera vez) y los valores llegan de Open Food Facts. Los revisas y queda guardado como producto propio, sin IA.
- **Productos con etiqueta.** Haces una foto a la tabla nutricional de un envase. La IA la lee, la revisas con la foto al lado y queda guardada. Desde entonces «dos yogures ligeros» usa sus cifras exactas multiplicadas por dos, también sin conexión.
- **Bebidas**, con su alcohol contado aparte (7 kcal por gramo) y fuera de los macros.
- **Copiar** una comida o un día entero a otro día, sin IA.
- **Favoritos y recientes** ordenados según el momento del día: el café arriba por la mañana, la cena por la noche.
- **Raciones** ×0,5, ×1, ×1,5, ×2 o a medida, y gramos por ingrediente: todo se recalcula en el móvil.
- **Importar** tu historial de MyFitnessPal, Yazio o cualquier CSV (con vista previa, columnas detectadas, aviso de duplicados y sin repetir nada si importas dos veces), o restaurar una exportación de Kcalia.

**Seguimiento**

- **Hoy:** anillo de calorías con lo que te queda, anillos de proteínas, hidratos y grasas, fibra orientativa y un mensaje según lo que falte («Te quedan 32 g de proteína: una lata de atún o 120 g de pavo y listo»).
- **Agua** con vasos de un toque y objetivo automático (35 ml por kilo) o a mano.
- **Peso** con gráfica y media móvil de 7 días; **medidas** (cintura, pecho, brazo, cadera, muslo) con su evolución; y **fotos de progreso** privadas, guardadas en tu servidor y nunca enviadas a la IA.
- **Diario por días** y **resumen semanal** calculado en código: adherencia, media diaria, balance frente a tu mantenimiento, mejor y peor día, tendencia de peso, comparación con la semana anterior y proyección. Racha, insignias y logros.
- **Compartir la semana como imagen** (1080 × 1350), con el menú de compartir del móvil o como descarga.

**Entrenamiento**

- **Días de entreno y de descanso** con objetivos propios: por defecto +200 kcal los días que entrenas y los de descanso bajan lo justo para compensarlo, de modo que la semana queda en tu objetivo (con 4 días de entreno, −270). También admite un ajuste fijo o cifras a mano. Se marca por día de la semana o día a día; en Hoy, «¿Entrenas hoy?» lo activa con un toque (y «Deshacer» lo revierte).
- **Registro de entrenos** en `/entreno`: rutinas de ejemplo (empuje, tirón, pierna, cuerpo completo) y las tuyas, series con peso y repeticiones, «Repetir» la anterior, temporizador de descanso, última marca de cada ejercicio, 1RM estimado y progresión. Funciona sin conexión.
- **Calorías del entreno** netas: (MET − 1) × peso × duración, sin volver a contar el gasto en reposo, con los MET del Compendium of Physical Activities 2024 (la cinta, la bici, el remo y la elíptica, cada uno con el suyo). Por defecto son solo una referencia; se pueden sumar al objetivo del día desde Ajustes.
- **Tu gasto real.** Con 4 semanas de lo que apuntas y de tu peso, Kcalia mide lo que gastas de verdad y te deja usarlo en lugar de la fórmula.

**Constancia**

- **Recordatorios** en el móvil (Web Push) para registrar cada comida y para pesarte, a las horas que elijas. Solo llegan si ese día aún no lo has hecho.
- **Plan semanal** con lo que ya sueles comer, macros de cada día frente a su objetivo, **lista de la compra** marcable que suma los ingredientes de la semana y, si quieres, ideas de la IA para rellenar huecos.
- **Cerrar el día:** a partir de la hora que elijas, si te quedan calorías, te sugiere qué comer con tus comidas y productos habituales sin pasarte, priorizando la proteína que falte. Sin IA, salvo que pidas ideas.

**Cuentas y datos**

- **Varias cuentas con aprobación manual.** La primera es la del administrador. Quien quiera usar tu instalación pide cuenta y espera a que la apruebes en `/admin`, donde también ves el gasto de IA, pones límites por cuenta, suspendes o reactivas y cierras el registro. Todo queda en una auditoría.
- **Tus datos son tuyos:** exportación a JSON y CSV, importación, borrado de datos o de la cuenta desde Ajustes, copia diaria y, opcionalmente, copia cifrada fuera del servidor.
- **PWA** instalable, con atajos en el icono (añadir comida, un vaso de agua, entrenar, peso), tema claro, oscuro o automático, y **sin conexión**: lo que ya conoce se apunta y se sincroniza al volver la red.

## Capturas

| | Oscuro | Claro |
|---|---|---|
| **Hoy** | <img src="docs/screenshots/dark/01-hoy.png" width="240" alt="Pantalla de hoy en modo oscuro" /> | <img src="docs/screenshots/light/01-hoy.png" width="240" alt="Pantalla de hoy en modo claro" /> |
| **Revisar y guardar** | <img src="docs/screenshots/dark/03-resultado.png" width="240" alt="Desglose de una comida en modo oscuro" /> | <img src="docs/screenshots/light/03-resultado.png" width="240" alt="Desglose de una comida en modo claro" /> |
| **Cerrar el día** | <img src="docs/screenshots/dark/12-sugerencia.png" width="240" alt="Sugerencias para cubrir las calorías y la proteína que faltan, en modo oscuro" /> | <img src="docs/screenshots/light/12-sugerencia.png" width="240" alt="Sugerencias para cubrir las calorías y la proteína que faltan, en modo claro" /> |
| **Entreno en marcha** | <img src="docs/screenshots/dark/15-entreno-activo.png" width="240" alt="Entreno en marcha con el descanso corriendo, en modo oscuro" /> | <img src="docs/screenshots/light/15-entreno-activo.png" width="240" alt="Entreno en marcha con el descanso corriendo, en modo claro" /> |
| **Plan semanal** | <img src="docs/screenshots/dark/13-plan.png" width="240" alt="Plan de la semana con las calorías de cada día frente a su objetivo, en modo oscuro" /> | <img src="docs/screenshots/light/13-plan.png" width="240" alt="Plan de la semana con las calorías de cada día frente a su objetivo, en modo claro" /> |
| **Historial** | <img src="docs/screenshots/dark/04-historial.png" width="240" alt="Historial con gráficas en modo oscuro" /> | <img src="docs/screenshots/light/04-historial.png" width="240" alt="Historial con gráficas en modo claro" /> |

<details>
<summary>Más pantallas: resumen, peso, medidas, rutinas, productos, administración, ajustes…</summary>

| Resumen semanal | Peso | Medidas | Rutinas |
|---|---|---|---|
| <img src="docs/screenshots/dark/05-resumen.png" width="200" alt="Resumen semanal" /> | <img src="docs/screenshots/dark/06-peso.png" width="200" alt="Seguimiento de peso con media móvil" /> | <img src="docs/screenshots/dark/16-medidas.png" width="200" alt="Evolución de la cintura" /> | <img src="docs/screenshots/dark/14-entreno.png" width="200" alt="Rutinas de entreno" /> |

| Añadir comida | Productos | Etiqueta leída | «Dos yogures ligeros con una manzana» |
|---|---|---|---|
| <img src="docs/screenshots/dark/02-anadir.png" width="200" alt="Hoja para añadir comida con favoritos, productos, bebidas y recientes" /> | <img src="docs/screenshots/dark/09-productos.png" width="200" alt="Lista de productos con la foto de su etiqueta" /> | <img src="docs/screenshots/dark/10-etiqueta.png" width="200" alt="Revisión de la etiqueta de un yogur con su foto y las cifras leídas" /> | <img src="docs/screenshots/dark/11-dos-yogures.png" width="200" alt="El yogur sale de la etiqueta guardada y la manzana de la IA" /> |

| Administración | Ajustes | Acceso | Tu plan |
|---|---|---|---|
| <img src="docs/screenshots/dark/17-admin.png" width="200" alt="Panel de administración con dos solicitudes de cuenta y el gasto de IA del día" /> | <img src="docs/screenshots/dark/07-ajustes.png" width="200" alt="Ajustes" /> | <img src="docs/screenshots/dark/00-acceso.png" width="200" alt="Inicio de sesión" /> | <img src="docs/screenshots/dark/08-plan.png" width="200" alt="Plan calculado tras el cuestionario inicial" /> |

**La semana, como imagen para compartir:**

<img src="docs/semana-compartida.png" width="300" alt="Imagen de la semana: porcentaje de días en objetivo, barras por día, media diaria, proteína media, días registrados y cambio de peso" />

</details>

Las capturas y los GIF salen de la app real con `scripts/capture_screenshots.py`, que la levanta con una IA simulada y datos de demostración temporales.

## Cómo se calculan las calorías

La IA es buena reconociendo qué hay en un plato y estimando raciones, y mala recordando cifras exactas o haciendo cuentas. Así que cada parte la hace quien mejor la hace:

| Qué | Quién | Cómo |
|---|---|---|
| Qué alimento es y cómo está cocinado | IA | Devuelve el alimento base («pechuga de pollo») y la preparación (crudo, cocido, plancha, horno, salteado, frito, rebozado, guisado o tal cual) |
| Cuánto hay, si nadie lo dice | IA | En fotos, por el tamaño del plato; en texto, con las raciones típicas españolas |
| Calorías y macros por 100 g | Tabla oficial | [CIQUAL 2025](https://ciqual.anses.fr/) (ANSES) y [USDA FoodData Central](https://fdc.nal.usda.gov/): 472 alimentos y 22 platos españoles por receta. Cifras copiadas sin alterar |
| Peso de una unidad | Tabla oficial | Parte comestible: un huevo M son 50 g sin cáscara; una loncha de jamón serrano, 15 g; una cucharada de aceite, 10 g |
| Mililitros a gramos | Tabla oficial | Con la densidad de cada líquido (aceite 0,915; leche 1,03; miel 1,42) |
| Aceite de cocinar | Código | Si no mencionas grasa: plancha 2 g, horno 3 g y salteado 5 g por cada 100 g de alimento (entre 2 y 10 g). Lo frito y lo rebozado ya lo llevan en su valor oficial: no se cuenta dos veces |
| Energía de lo que no está en la tabla | Código | Con los factores del Reglamento (UE) 1169/2011: 4 kcal/g de proteína e hidratos, 9 de grasa, 2 de fibra y 7 de alcohol |

Todo pasa por la misma canalización (`backend/app/refine.py`), venga del texto, la voz, una foto, el plan semanal, las sugerencias o el historial. Por eso la misma comida da siempre las mismas calorías: «pechuga de pollo con arroz» analizada por la IA y «150 g de pollo a la plancha y 200 g de arroz» resuelta sin IA dan exactamente lo mismo.

El emparejado con la tabla es estricto a propósito: «huevo a la plancha» no toma el valor de «huevo frito» ni «pechuga de pavo» el de «pechuga de pollo». Si no hay una coincidencia clara se queda la estimación de la IA, marcada como tal. Si escribes algo tuyo («con un chorrito de AOVE», «sin aceite») manda lo que dices. Los ingredientes que añades a mano tienen prioridad sobre la tabla, y la tabla sobre lo aprendido de la IA. Lo que apuntaste antes de la tabla conserva sus gramos e ingredientes, pero al repetirlo toma los valores oficiales.

**Medido con la clave real.** 30 comidas con cantidades y 10 sin ellas, contra los valores oficiales de esas cantidades (`python -m app.bench`):

| | Antes (solo la IA) | Ahora (IA + tabla) |
|---|---|---|
| Error medio de calorías | 15,8 % | 0,2 % |
| Dentro de ±12 % | 21 de 30 | 30 de 30 |
| Error medio por macro | 1,8 g | 0,0 g |
| Comidas sin cantidades en rango | 8 de 10 | 8 de 10 |

Medido el 14 de octubre de 2026 con la IA real. Algunos ejemplos de antes: un huevo frito salía a 197 kcal (oficial: 88), 150 g de patatas fritas a 468 (387, con el aceite contado dos veces) y un café con leche a 157 (73). Ahora las 30 comidas con cantidades dan el valor oficial salvo redondeos. En las comidas sin cantidades lo que queda es la estimación de la ración, que hace la IA; las dos que se salieron del rango fueron un bocadillo (la IA pesó el pan como una rebanada) y una ensalada mixta a 1 kcal del mínimo. Latencia mediana de 4,1 s y unos 2.900 tokens de entrada por comida.

## Cómo se ahorra IA

Cada consulta a un modelo cuesta dinero y tiempo. La mayoría de lo que comemos se repite, así que antes de llamar a la IA Kcalia intenta resolver la comida con lo que ya sabe:

```mermaid
flowchart TD
    A["Texto, o audio ya transcrito"] --> N["Normalizar<br/>minúsculas, sin tildes, artículos ni signos;<br/>«dos» → 2, «200gr» → 200 g"]
    N --> B{"¿Idéntica a una<br/>comida del historial?"}
    B -- Sí --> OK1["Se añade directamente"]
    B -- No --> C{"¿Se parece ≥ 0,85<br/>a alguna?"}
    C -- Sí --> Q["«¿Es esta comida?»"]
    Q -- "Sí, es esta" --> OK2["Se añade y se recuerda<br/>esa forma de escribirla"]
    Q -- "No, es otra" --> P
    C -- No --> P{"¿Alguna parte es un producto<br/>con etiqueta guardada?"}
    P -- "Todo cubierto" --> OK4["Se multiplica la etiqueta<br/>por la cantidad"]
    P -- "Solo parte, o nada" --> D{"¿Todos los ingredientes están<br/>en la tabla oficial o en la caché?"}
    D -- Sí --> OK3["Se compone con sus<br/>valores y cantidades"]
    D -- No --> L{"¿Queda cupo<br/>de IA hoy?"}
    L -- Sí --> IA["Consulta a la IA<br/>JSON validado, un reintento"]
    L -- No --> STOP["Aviso: límite de hoy alcanzado"]
    IA --> LEARN["Se guarda la comida y sus<br/>ingredientes para la próxima vez"]
```

1. **Coincidencia exacta.** El texto se normaliza (minúsculas, sin tildes, sin artículos ni signos, números y unidades en forma canónica) y se busca en tu historial. «Un café con leche» y «café con leche!» son la misma comida.
2. **Coincidencia aproximada.** Si se parece mucho a algo que ya tienes (similitud ≥ 0,85), te lo pregunta con un toque. Hay dos salvaguardas para no confundir comidas distintas: las cantidades tienen que coincidir («2 huevos» no es «3 huevos») y cada palabra debe tener su pareja («pechuga de pollo» no es «pechuga de pavo»).
3. **Productos con etiqueta o código de barras.** «Dos yogures ligeros» se calcula con sus cifras exactas por 2. Si solo una parte es de un producto («dos yogures ligeros con un cachopo»), a la IA solo va «un cachopo».
4. **Tabla oficial y caché de ingredientes.** «200 g de arroz y 150 g de pollo a la plancha» o «2 huevos fritos y una tostada» se resuelven con la tabla oficial, sin IA y con el aceite de cocinar calculado. Lo que no está en la tabla se aprende de cada respuesta de la IA (valores por 100 g y peso de la unidad) para la próxima vez.
5. **IA**, solo si nada de lo anterior encaja, con tres topes: por cuenta (`AI_USER_DAILY_LIMIT`), global para toda la instalación (`AI_DAILY_LIMIT`) y uno aparte para el administrador.

Los pasos 1, 2 y 3 también se hacen en el propio móvil: por eso son instantáneos y funcionan sin conexión. La normalización existe dos veces, en Python y en TypeScript, y ambas se prueban contra el mismo fichero de casos para que no diverjan. Lo mismo pasa con los objetivos de los días de entreno y de descanso.

En **Ajustes** hay un contador de consultas ahorradas, desglosado por cada vía. Las sugerencias para cerrar el día, el plan semanal, copiar comidas, el código de barras y la importación no usan IA; las ideas de la IA son siempre un botón aparte.

## Cómo se calculan los objetivos

Sin IA y sin cajas negras: la app enseña el cálculo paso a paso.

1. **Metabolismo basal** con Mifflin-St Jeor: `10 × peso + 6,25 × altura − 5 × edad`, `+5` en hombres y `−161` en mujeres.
2. **Mantenimiento**: basal × factor de actividad (1,2 · 1,375 · 1,465 · 1,55 · 1,725 · 1,9). Cada nivel describe a la vez cómo es el día y cuántos días se entrena: «Medio» (×1,465) es para quien pasa el día sentado y entrena 4-5 días, el caso que antes caía entre «Ligero», que se quedaba corto, y «Moderado», que se pasaba. Si hay dudas, mejor el nivel de abajo: el gasto real medido lo corrige después.
3. **Ajuste según el objetivo:**

| Objetivo | Calorías | Proteína | Grasas |
|---|---|---|---|
| Definición ligera | −15 % | 2,0 g/kg | 0,9 g/kg |
| Definición agresiva | −25 % | 2,2 g/kg | 0,8 g/kg |
| Mantenimiento | 0 % | 1,8 g/kg | 0,9 g/kg |
| Recomposición | −2,5 % | 2,2 g/kg | 0,9 g/kg |
| Volumen | +7,5 % | 1,8 g/kg | 1,0 g/kg |

4. **Hidratos**: las calorías que quedan, a 4 kcal por gramo.
5. **Días de entreno y de descanso** (opcional): el ajuste de cada tipo de día se suma o resta a las calorías y lo absorben los hidratos; proteína y grasa no cambian. Por defecto, los días de descanso compensan los de entreno (−ajuste × días de entreno ÷ días de descanso, redondeado a 10 kcal), así la media semanal es el objetivo del plan. El nivel de actividad ya incluye el gimnasio, y sumar en los días de entreno sin restar en los demás lo contaría dos veces. Los niveles de actividad se describen por cómo es el día entero (sentado, de pie, trabajo físico), no por los días de gimnasio.
6. **Gasto real** (opcional): la fórmula del paso 2 puede desviarse un 10-20 %. Con las últimas 4 semanas, Kcalia calcula `media de lo comido − tendencia del peso × 7.700 kcal/kg`. Solo cuenta días con al menos la mitad del objetivo apuntado (hacen falta 10) y la pendiente de al menos 4 pesajes repartidos en 10 días, y lo mezcla con la fórmula hasta tener 3 semanas de datos. Si el resultado no es creíble (por agua o registros incompletos) lo explica y no lo ofrece. Desde Ajustes → Cómo se calculan puedes usarlo como mantenimiento o volver a la fórmula; con él, las calorías del entreno ya van incluidas y no se suman aparte.

**Avisos de seguridad.** El plan nunca baja de 1.200 kcal en mujeres ni de 1.500 en hombres, ni propone un déficit mayor de 1.000 kcal al día. Con un IMC por debajo de 18,5 no aplica déficit y lo dice. Con un IMC por encima de 30 calcula proteína y grasa con un peso de referencia. Avisa si el objetivo queda por debajo del metabolismo basal, si eres menor de edad o si el peso objetivo no cuadra con el plan. Son orientaciones generales, no consejo médico.

## Arquitectura

```mermaid
flowchart LR
    subgraph movil["Tu móvil"]
        PWA["PWA (React)<br/>service worker<br/>caché y cola offline en IndexedDB"]
    end
    subgraph vps["Tu VPS"]
        Caddy["Caddy del host<br/>HTTPS con Let's Encrypt"]
        subgraph red["Red Docker kcalia_net"]
            App["kcalia-app<br/>FastAPI + frontend compilado<br/>tareas: copias, avisos, resúmenes"]
            STT["kcalia-stt<br/>Whisper en CPU"]
        end
        DB[("SQLite<br/>volumen kcalia-data")]
        BK[("Copias diarias<br/>volumen kcalia-backups")]
    end
    IA["Proveedor de IA<br/>compatible con OpenAI"]
    OFF["Open Food Facts"]
    PUSH["Servicios de push<br/>Apple, Google, Mozilla"]
    S3[("Almacenamiento S3<br/>opcional, cifrado")]

    PWA -- HTTPS --> Caddy
    Caddy -- "127.0.0.1:8095" --> App
    App --> DB
    App -- "cada noche" --> BK
    BK -. "copia externa" .-> S3
    App -- audio --> STT
    App -- "solo si hace falta" --> IA
    App -- "códigos de barras" --> OFF
    App -- "recordatorios cifrados" --> PUSH
    PUSH -.-> PWA
```

- **Un contenedor para la app**: FastAPI sirve la API y el frontend ya compilado. Las claves (IA, push, almacenamiento) viven solo ahí; el navegador nunca las ve.
- **Un contenedor para la voz**: faster-whisper con una API compatible con OpenAI. Carga el modelo en la primera petición y lo libera tras diez minutos sin uso.
- **Sin puertos abiertos**: la app escucha solo en `127.0.0.1` y el servicio de voz solo dentro de su red Docker. El HTTPS lo pone el Caddy que ya tenga el host.
- **Tareas periódicas en el propio proceso**: copia diaria (y subida externa con reintentos), recordatorios cada minuto y resumen semanal del domingo, sin cron externo.
- **Migraciones de esquema** numeradas con `PRAGMA user_version`. Antes de migrar se guarda una copia comprimida y cada migración se prueba sobre una base de demostración con datos: nunca se pierde nada al actualizar.
- **Sin conexión**: la caché de datos se guarda en IndexedDB y todo lo que se escribe (comidas, agua, peso, medidas, entrenos, plan) va a una cola. Cada cambio lleva un identificador generado en el móvil, así que reenviar la cola no duplica nada.
- **Notificaciones propias**: Web Push con cifrado `aes128gcm` (RFC 8291) y firma VAPID implementados con `cryptography` y probados con el vector de la RFC.

```
backend/    API, cálculos, coincidencias, resumen, entrenos, avisos, copias e importación (Python)
frontend/   PWA (React + TypeScript), sistema de diseño en tokens CSS
stt/        Servicio de transcripción (faster-whisper)
e2e/        Pruebas de extremo a extremo e IA simulada para pruebas
deploy/     Despliegue en VPS y bloque de Caddy
scripts/    Clave de IA, claves VAPID, administrador, restaurar copias, iconos y capturas
docs/       Decisiones, guía del atajo de iPhone, capturas
```

## Seguridad y privacidad

- **Aislamiento entre cuentas.** Cada tabla con datos personales lleva su `user_id` y la sesión de base de datos filtra todas las consultas automáticamente por la cuenta que hace la petición. Si algún código intentara leer o escribir datos sin una cuenta asignada, falla en lugar de mezclar datos. Hay pruebas que crean dos cuentas y comprueban cada ruta de la API, y se verificó que fallan si se quita el filtro.
- **Acceso.** Todas las rutas de la API exigen sesión y cuenta aprobada, salvo salud, inicio de sesión, registro, estado y cierre de sesión; una prueba recorre todas las rutas registradas para que una nueva no se quede abierta por descuido. `/admin` exige el rol de administrador, que solo se asigna en la migración inicial o con un script en el servidor.
- **Registro y entrada.** Contraseñas con Argon2 (mínimo 10 caracteres, sin contener el usuario). Espera creciente tras fallos desde la misma conexión (bloqueo tras 5), misma respuesta y mismo tiempo exista o no la cuenta, límite de solicitudes por IP, campo trampa contra bots y un máximo de solicitudes pendientes. Un ataque repartido entre muchas IP contra un usuario solo frena unos minutos a conexiones nuevas: nadie puede dejarte fuera de tu cuenta desde la conexión que ya usas.
- **Gasto controlado.** Topes de IA y de voz por cuenta, global y del administrador, interruptor para pausar la IA y precio estimado por día y por mes en `/admin`.
- **Cabeceras**: CSP estricta, HSTS con subdominios, `X-Frame-Options`, `nosniff`, COOP y CORP `same-origin`, Permissions-Policy que apaga lo que la app no usa y sin cabecera `Server`. Cookies `HttpOnly` + `Secure` + `SameSite` y comprobación de origen en las peticiones que cambian datos.
- **Entradas acotadas.** Peticiones de 1 MiB como mucho en JSON y 16 MiB en total (en Caddy y en la app). Las imágenes se aceptan solo si sus bytes son JPEG, PNG o WebP, y se sirven con el tipo detectado, no con el que dijo el navegador. Las notificaciones push solo se envían a los servicios reales (Google, Mozilla, Apple, Microsoft), nunca a direcciones internas. Las exportaciones CSV neutralizan las celdas que empiezan por `=`, `+`, `-` o `@`.
- **Contenedor.** Usuario sin privilegios, sistema de archivos de solo lectura, sin capacidades de Linux, `no-new-privileges`, memoria limitada y el puerto solo escucha en `127.0.0.1` detrás de Caddy (TLS 1.2 y 1.3).
- **Privacidad**: las fotos de progreso nunca van a la IA; el código de barras solo envía el número a Open Food Facts; las copias externas pueden ir cifradas con AES-256-GCM con una frase que solo tienes tú.

- **Probada a romperla.**
  - Entradas absurdas: `tests/test_fuzz.py` manda a las 102 operaciones de la API cuerpos vacíos o del tipo equivocado, JSON roto, `NaN`, números enormes, textos de 100.000 caracteres, nulos, Unicode roto, fechas extremas e identificadores imposibles. Falla ante cualquier error 500 o respuesta lenta.
  - Concurrencia: si dos escrituras simultáneas chocan en un índice único, la petición se repite en vez de fallar (`app/conflicts.py`). Probado con 300 peticiones a la vez: ninguna falla y no se pierde ningún dato.
  - Fallos al dibujar: un fallo en una pantalla muestra un aviso con «Reintentar» y «Borrar la copia de este dispositivo y recargar», en vez de dejarla en blanco.
  - Datos extremos: `e2e/test_zz_extremos.py` prueba nombres de longitud máxima y comidas de 180.000 kcal en un móvil de 375 px, el doble envío, exportar e importar, y una copia local corrupta.
- **Contraseña.** Se cambia en Ajustes → Cuenta: pide la actual y cierra las sesiones de los demás dispositivos. Las confirmaciones con contraseña (borrar datos, borrar la cuenta, cambiarla) tienen un freno por cuenta, así que con una sesión robada no se pueden probar contraseñas sin límite.

- **Vigilancia.**
  - Errores 500: cada uno queda en la lista de errores recientes del panel (`/api/admin/overview` → `errors`) y el administrador recibe un push como mucho cada 15 minutos (`app/notify.py`). Solo se guardan el tipo de error y la ruta, nunca datos.
  - Web caída: desde fuera, el workflow `Disponibilidad` de GitHub comprueba `kcalia.space` cada 15 minutos. Si no responde tras tres intentos, abre una incidencia, que avisa por correo, y la cierra al volver.
  - Copias: cada lunes, `app/backupcheck.py` abre de verdad la última copia local y, si existe, la externa descifrada. Comprueba la integridad, que tiene datos y su antigüedad, y avisa si algo falla.

Cómo avisar de un fallo de seguridad y qué se revisó: [SECURITY.md](SECURITY.md).

## Stack

| Capa | Tecnologías |
|---|---|
| API | Python 3.12, FastAPI, SQLAlchemy 2, SQLite (WAL), Pydantic, Argon2, rapidfuzz, httpx, cryptography |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS 4, Motion, Recharts, TanStack Query, Lucide, Geist auto-hospedada |
| PWA | vite-plugin-pwa (Workbox), IndexedDB, Web Push, BarcodeDetector con zxing-wasm de respaldo |
| Voz | faster-whisper (CTranslate2) en CPU |
| IA | Claude Haiku 5.5 (Anthropic, SDK oficial); también vale cualquier proveedor compatible con la API de OpenAI |
| Infraestructura | Docker Compose, Caddy, GitHub Actions |
| Pruebas | pytest, Vitest, Playwright |

**Diseño.** Todos los colores, radios, sombras y duraciones salen de `frontend/src/styles/tokens.css`. Cada macro tiene siempre el mismo color (calorías de naranja a esmeralda según avanza, proteínas índigo, hidratos ámbar, grasas rosa) y nunca va solo: lo acompañan su letra (P, H, G) y su icono. La paleta se comprobó con simulación de daltonismo. Las animaciones respetan `prefers-reduced-motion`.

## Puesta en marcha con Docker

Necesitas Docker con Compose y la clave de un proveedor de IA compatible con OpenAI.

```bash
git clone https://github.com/Alvaro-Rovira/kcalia.git
cd kcalia
cp .env.example .env
```

Para probarlo en tu ordenador, sin proxy ni HTTPS, añade estas dos líneas a `.env`:

```bash
COOKIE_SECURE=false
GZIP=true
```

Guarda la clave de la IA (el script la pide sin mostrarla), genera las claves de las notificaciones (tampoco se muestran) y arranca:

```bash
./scripts/set-ai-key.sh
```

```bash
python3 scripts/gen-vapid.py --env-file .env
```

```bash
docker compose up -d --build
```

Abre <http://localhost:8095>, elige «Créala ahora» y crea tu cuenta: la primera es la del administrador.

El primer arranque tarda unos minutos: compila el frontend y descarga el modelo de voz (unos 460 MB con `small`). Las imágenes ocupan unos 300 MB la app y 1,8 GB la de voz.

Sin clave de IA la app funciona igual para todo lo que no sea analizar comidas nuevas; sin claves VAPID, todo salvo las notificaciones.

## Variables de entorno

Todas viven en `.env`. `.env.example` las trae comentadas; las que no pongas usan el valor por defecto.

| Variable | Por defecto | Para qué sirve |
|---|---|---|
| `DOMAIN` | `kcalia.space` | Dominio público. Es el único sitio donde aparece. |
| `REDIRECT_DOMAINS` | `www.kcalia.space` | Dominios que redirigen con 301 al principal (www, dominios antiguos), separados por espacios. |
| `APP_PORT` | `8095` | Puerto local (solo loopback) al que llega el proxy. |
| `TZ` | `Europe/Madrid` | Zona horaria para las copias, los recordatorios y el resumen del domingo. |
| `AI_MODEL` | `claude-haiku-5-5` | Modelo para el texto. Los `claude-...` van por el SDK de Anthropic. |
| `ANTHROPIC_API_KEY` | vacío | Clave de Claude. Se rellena con `scripts/set-ai-key.sh ANTHROPIC_API_KEY`. |
| `AI_EFFORT` | `low` | Razonamiento de Claude: vacío lo desactiva; `low`, `medium` o `high`. |
| `AI_BASE_URL`, `AI_API_KEY` | vacío | Solo para un proveedor compatible con OpenAI (un `AI_MODEL` que no empiece por `claude-`). |
| `AI_VISION_MODEL` | vacío | Modelo para las fotos. Vacío usa `AI_MODEL`. |
| `AI_VISION_BASE_URL`, `AI_VISION_API_KEY` | vacío | Solo si quieres otro proveedor para las fotos. |
| `AI_DAILY_LIMIT` | `60` | Tope global de consultas de IA al día, sumando todas las cuentas. |
| `AI_USER_DAILY_LIMIT` | `20` | Tope por cuenta y día (se puede cambiar a cada cuenta en `/admin`). |
| `ADMIN_AI_DAILY_LIMIT` | `0` | Tope propio del administrador, aparte del global. `0` = igual que `AI_DAILY_LIMIT`. |
| `AI_PRICE_INPUT`, `AI_PRICE_OUTPUT` | `0.10`, `0.50` | Dólares por millón de tokens, para estimar el gasto en `/admin`. |
| `AI_TIMEOUT` | `45` | Segundos de espera máxima a la IA. |
| `WHISPER_MODEL` | `small` | Modelo de voz: `tiny`, `base`, `small` o `medium`. |
| `WHISPER_THREADS` | `3` | Hilos de CPU para transcribir. |
| `STT_DAILY_LIMIT`, `STT_USER_DAILY_LIMIT` | `100`, `30` | Topes de audios al día: global y por cuenta. |
| `STT_PRICE_PER_CALL` | `0` | Coste estimado de cada audio (0 con el Whisper propio). |
| `STT_BASE_URL`, `STT_API_KEY`, `STT_MODEL` | contenedor propio | Para usar un servicio de voz externo compatible con OpenAI. |
| `ALLOW_SIGNUP` | `true` | `false` = nadie puede pedir cuenta. También se cierra desde `/admin`. |
| `MAX_PENDING_ACCOUNTS` | `20` | Máximo de solicitudes pendientes a la vez. |
| `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY` | vacío | Claves de las notificaciones. Se generan con `scripts/gen-vapid.py`. |
| `VAPID_SUBJECT` | `https://DOMAIN` | Contacto para los servicios de push (`mailto:` o `https:`). |
| `SUGGEST_MIN_KCAL` | `80` | Calorías restantes a partir de las que se sugiere cómo cerrar el día. |
| `SESSION_DAYS` | `180` | Duración de la sesión; se renueva con el uso. |
| `BACKUP_KEEP` | `7` | Copias diarias locales que se conservan. |
| `BACKUP_REMOTE_URL`, `BACKUP_REMOTE_BUCKET` | vacío | Destino S3 compatible para la copia externa (R2, B2, S3, MinIO…). |
| `BACKUP_REMOTE_ACCESS_KEY`, `BACKUP_REMOTE_SECRET_KEY` | vacío | Credenciales de ese destino. |
| `BACKUP_REMOTE_PREFIX`, `BACKUP_REMOTE_REGION`, `BACKUP_REMOTE_KEEP` | `kcalia/`, `auto`, `30` | Carpeta, región y copias que se conservan fuera. |
| `BACKUP_ENCRYPTION_KEY` | vacío | Frase para cifrar las copias externas. Guárdala aparte. |
| `COOKIE_SECURE` | `true` | `false` solo para probar en `http://localhost`. |
| `GZIP` | `false` | Compresión desde la propia app; útil sin proxy delante. |

## Despliegue en una VPS

Pensado para un servidor que ya tiene otros proyectos: red y volúmenes propios, ningún puerto abierto al exterior, límites de memoria (384 MB la app, 1,5 GB la voz), sistema de ficheros de solo lectura, sin privilegios y con rotación de logs. El despliegue solo toca lo de Kcalia.

Requisitos: Docker con Compose, Caddy instalado en el host y el dominio apuntando a la VPS.

```bash
DEPLOY_HOST=usuario@tu-servidor ./deploy/deploy.sh
```

El script, en este orden:

1. Clona o actualiza el repositorio en `/opt/kcalia` (solo avance rápido de `main`).
2. Crea `.env` a partir de `.env.example` si no existe; si ya existe, **añade solo las variables nuevas** con su valor por defecto, sin mostrar ni cambiar las que tienes.
3. Construye las imágenes y, si faltan, genera las claves VAPID dentro del contenedor y las guarda en `.env` sin mostrarlas.
4. Arranca los contenedores. Al arrancar, la app migra la base de datos si hace falta, guardando antes una copia en el volumen de copias.
5. Ejecuta `deploy/caddy-site.sh`, que añade **solo** el bloque de Kcalia al `Caddyfile` del host: el dominio principal con HTTPS de Let's Encrypt (Caddy lo renueva solo), las redirecciones 301 de `REDIRECT_DOMAINS` y de HTTP a HTTPS. Hace copia antes, valida la configuración y, si no valida, restaura la copia y no recarga. Con `--check` solo enseña el bloque y lo valida.
6. Comprueba que `https://$DOMAIN/api/health` responde.

**La clave de la IA** se pone en el servidor sin que pase por ningún chat ni quede en el historial de la terminal:

```bash
ssh -t root@TU_SERVIDOR /opt/kcalia/scripts/set-ai-key.sh
```

```bash
ssh root@TU_SERVIDOR 'cd /opt/kcalia && docker compose up -d app'
```

Comandos útiles, ya dentro del servidor y en `/opt/kcalia`:

```bash
docker compose ps
```

```bash
docker compose logs -f --tail=100 app
```

## Cuentas y administración

- La **primera cuenta** que se crea es la del administrador. Al actualizar una instalación anterior de una sola cuenta, la migración la convierte en administradora y conserva todos sus datos.
- Las demás personas eligen «Créala ahora», ven «Solicitud enviada» y esperan. Al administrador le llega una notificación (si las tiene activadas) y un aviso en Ajustes.
- En **`/admin`**: aprobar, rechazar, suspender o reactivar cuentas; ver el uso de IA y voz de cada una con su coste estimado; cambiar sus límites; pausar la IA para todos; abrir o cerrar el registro; ver el estado de la copia externa y la auditoría de todo lo anterior.
- El rol de administrador no se puede asignar desde la interfaz ni desde la API. Para pasarlo a otra cuenta, en el servidor:

```bash
cd /opt/kcalia && docker compose exec -T app python - OTRA_CUENTA < scripts/make-admin.py
```

## Migrar a un dominio propio

El dominio es una sola variable. Para cambiarlo (así se pasó de `kcalia.roviradev.duckdns.org` a `kcalia.space`):

1. Apunta los registros `A` del dominio nuevo y de su `www` a la IP de la VPS.
2. En `/opt/kcalia/.env`, cambia `DOMAIN` y añade el dominio antiguo a `REDIRECT_DOMAINS`:

```bash
DOMAIN=kcalia.space
REDIRECT_DOMAINS=www.kcalia.space kcalia.roviradev.duckdns.org
```

3. Aplica el cambio:

```bash
cd /opt/kcalia && docker compose up -d app && ./deploy/caddy-site.sh
```

Caddy pide los certificados nuevos solo y los renueva antes de que caduquen. El dominio antiguo y el `www` responden con una redirección 301 al nuevo, conservando la ruta. Si alguien tenía la app instalada desde el dominio antiguo, el dominio antiguo le sirve un service worker que da de baja el anterior y le lleva al nuevo, porque si no seguiría abriéndose desde la caché. Para el navegador es un sitio distinto: hay que iniciar sesión otra vez, reinstalar la app en el móvil y volver a activar las notificaciones. Tus datos siguen en el servidor.

## Instalar la app en el móvil

**iPhone y iPad (Safari)**

1. Abre la dirección de tu instalación en **Safari**.
2. Pulsa **Compartir**.
3. Elige **Añadir a pantalla de inicio** y confirma.

Se abre a pantalla completa, con su icono y su pantalla de arranque. Las notificaciones funcionan en iOS 16.4 o posterior con la app instalada así. Para apuntar por voz con Siri, sigue la guía de **Ajustes → Atajos → Atajo de voz en iPhone** (también en [`docs/ATAJO-IOS.md`](docs/ATAJO-IOS.md)).

**Android (Chrome)**

Menú del navegador e **Instalar aplicación**, o desde **Ajustes → Instalar como app** dentro de Kcalia. Manteniendo pulsado el icono aparecen los atajos: añadir comida, un vaso de agua, entrenar y apuntar el peso.

Cuando hay una versión nueva, la app muestra un aviso con el botón «Actualizar».

## Elegir el modelo de IA

Por defecto, **Claude Haiku 5.5** para texto, fotos y etiquetas, con el SDK oficial de Anthropic. Recibe el formato de respuesta como salida estructurada (JSON con esquema, garantizado) y las fotos como bloque de imagen, con razonamiento bajo (`AI_EFFORT=low`). La clave se guarda con `scripts/set-ai-key.sh ANTHROPIC_API_KEY`. Cambiar de modelo es cambiar `AI_MODEL` (y `AI_VISION_MODEL` si quieres otro para las fotos). Un modelo que no empiece por `claude-` va por cualquier proveedor compatible con OpenAI (`AI_BASE_URL` y `AI_API_KEY`). Si ese proveedor rechaza algún parámetro, se reintenta con lo mínimo.

Para decidir con datos y no con impresiones hay dos herramientas. La de texto mide contra 40 comidas de referencia: 30 con cantidades, cuya referencia son los valores de la tabla oficial, y 10 sin ellas, con un rango aceptable. La de fotos usa platos reales pesados en báscula. Las dos dan error, latencia y coste, usan la clave que ya está en el contenedor y no la muestran. Con `--raw`, la de texto mide la IA sola, sin la tabla.

```bash
docker compose exec app python -m app.bench --price-in 0.10 --price-out 0.50
python3 -I scripts/fetch_nutrition5k.py /root/n5k      # 20 platos de Nutrition5k (Google Research, CC BY 4.0)
docker compose run --rm --no-deps -T -v /root/n5k:/n5k:ro app python -m app.bench_photos /n5k --model claude-haiku-5-5 --passes 2
```

**Claude Haiku 5.5, medido el 16 de octubre de 2026** (dos pasadas, porque las respuestas varían de una vez a otra):

| | Sin razonamiento | `AI_EFFORT=low` |
|---|---|---|
| Texto: error medio de calorías (30 con cantidades) | 4,7 % y 0,7 % | 1,5 % |
| Texto: dentro de ±12 % | 29/30 y 30/30 | 29/30 |
| Texto: comidas sin cantidades en rango | 8/10 y 8/10 | 8/10 |
| Texto: latencia mediana | 1,7 s | 2,0 s |
| Fotos: error mediano de calorías ([Nutrition5k](https://github.com/google-research-datasets/Nutrition5k), 18 platos) | 68 % | 41 % |
| Fotos: dentro de ±30 % | 9/36 | 11/36 |
| Fotos: latencia mediana | 2,5 s | 3,3 s |
| Coste | 0,06 $/100 comidas · 0,08 $/100 fotos | 0,06 $/100 comidas · 0,10 $/100 fotos |

En texto casi todas las cifras las pone la tabla oficial, y el fallo ocasional es una comida que el modelo descompone de otra forma (el café con leche). En fotos el modelo estima los gramos a ojo. Antes tendía a pasarse con las raciones pequeñas (+22 %), porque usaba las raciones típicas. Ahora las instrucciones de foto le piden pesar lo que se ve y contar las piezas: el error mediano bajó del 54 al 41 % y el sesgo a +9 % (la columna sin razonamiento es de antes de ese cambio). Añadir una frase a la foto («150 g de pollo») mejora mucho el resultado.

**Límites del proveedor.** Algunas cuentas traen un tope de peticiones por minuto. Si lo alcanzas, Kcalia espera un instante y reintenta una vez; si sigue, te lo explica en lugar de mostrar un error genérico. Para medir con una cuenta así, añade `--rpm N` a las herramientas.

**Por qué el modelo da valores «por 100 g».** En la primera prueba real, un modelo escaló dos veces el huevo (314 kcal en lugar de 157). Multiplicar es justo lo que un modelo hace mal y un programa nunca, así que el modelo aporta el conocimiento (calorías y macros por cada 100 g, y el peso del ingrediente) y el código hace la cuenta.

## Copias de seguridad

**Local.** Cada noche se guarda una copia consistente de la base de datos, comprimida, en el volumen `kcalia-backups`. Se conservan las siete últimas (`BACKUP_KEEP`). Antes de cada migración de esquema se guarda otra, `premigracion-*.db.gz`.

```bash
docker compose exec app ls -lh /backups
```

**Fuera del servidor (opcional).** Con `BACKUP_REMOTE_*` configurado, la copia nocturna se sube a cualquier almacenamiento compatible con S3 (Cloudflare R2, Backblaze B2, AWS S3, MinIO…) con firma SigV4. Se comprueba la integridad al subir (Content-MD5) y después (tamaño y SHA-256 del objeto guardado), se reintenta si falla y se conservan las `BACKUP_REMOTE_KEEP` más recientes. Con `BACKUP_ENCRYPTION_KEY`, se cifra antes de salir (AES-256-GCM, clave derivada con scrypt). El estado de la última subida se ve en `/admin`, y si falla, también en Ajustes del administrador.

**Restaurar.** `scripts/restore-backup.py` convierte una copia, local o descargada, cifrada o no, en una base de datos lista y comprueba que está íntegra:

```bash
python3 scripts/restore-backup.py kcalia-2026-10-06.db.gz.enc kcalia.db
```

Para ponerla en marcha (con la app parada):

```bash
docker compose stop app
```

```bash
docker run --rm -v kcalia_kcalia-data:/data -v "$PWD":/src alpine sh -c "cp /src/kcalia.db /data/kcalia.db && rm -f /data/kcalia.db-wal /data/kcalia.db-shm && chown 10001 /data/kcalia.db"
```

```bash
docker compose start app
```

## Desarrollo y pruebas

Necesitas [uv](https://docs.astral.sh/uv/) y Node 24.

```bash
make test
```

```bash
make e2e
```

`make dev` indica cómo arrancar la API con la IA simulada y el frontend con recarga en caliente. Ninguna prueba llama a servicios reales: la IA, Open Food Facts, los servicios de push y el almacenamiento S3 se simulan.

| Qué se prueba | Dónde | Pruebas |
|---|---|---|
| Acceso: cada ruta de la API sin sesión, pendiente, suspendida y sin ser administrador | `backend/tests/test_access.py` | 111 |
| Aislamiento entre cuentas, registro, inicio de sesión, límites y panel de administración | `test_isolation.py`, `test_accounts.py`, `test_daily.py`, `test_admin.py`, `test_make_admin.py` | 32 |
| Migraciones sobre una base de demostración con datos | `test_migrations.py` | 6 |
| Tabla de alimentos: cifras literales de la fuente, alias sin choques, energía coherente, emparejado estricto | `test_foodtable.py`, `test_foodtable_data.py` | 115 |
| Canalización de las comidas (gramos, aceite, energía UE), resolución sin IA, historial y banco | `test_refine.py`, `test_api_table.py`, `test_bench.py` | 62 |
| Gasto real con datos simulados y su API | `test_expenditure.py` | 11 |
| Metabolismo basal, objetivos, días de entreno y descanso (con la compensación semanal) | `test_nutrition.py`, `test_daytargets.py` | 41 |
| Normalización, similitud, coincidencias y productos | `test_textnorm.py`, `test_matching.py`, `test_products.py`, `test_api_products.py` | 117 |
| IA (comidas, etiquetas, plan, sugerencias; Claude y proveedores compatibles con OpenAI), código de barras y API completa | `test_ai.py`, `test_claude.py`, `test_barcode.py`, `test_api.py` | 81 |
| Agua, medidas, fotos, entrenos, plan, sugerencias e importación | `test_tracking.py`, `test_training.py`, `test_planner.py`, `test_suggest.py`, `test_importer.py` | 42 |
| Refuerzos de seguridad, fuzzing de las 102 operaciones, escrituras simultáneas y cambio de contraseña | `test_hardening.py`, `test_fuzz.py`, `test_conflicts.py`, `test_password.py` | 33 |
| Web Push (vector de la RFC 8291), recordatorios, VAPID | `test_webpush.py`, `test_push.py`, `test_gen_vapid.py` | 12 |
| Copias: firma SigV4 (ejemplo oficial de AWS), cifrado, subida verificada, retención | `test_offsite.py`, `test_jobs.py` | 13 |
| Resumen semanal y HTML servido | `test_summary.py`, `test_spa.py` | 16 |
| Audio de Chrome, Safari y Firefox decodificado para Whisper | `stt/test_audio.py` | 5 |
| Formato es-ES, espejos de la normalización, de los objetivos y de las calorías del entreno, origen de los valores, sugerencias (propiedades sobre 2.000 escenarios), entrenos, compra, atajos, cola sin conexión… | `frontend/src/**/*.test.ts` | 210 |
| Flujos completos en un móvil de 390 px | `e2e/test_flow.py` | 28 |
| Datos extremos en 375 px, doble envío, exportar e importar y copia local corrupta | `e2e/test_zz_extremos.py` | 3 |

Las pruebas de extremo a extremo levantan la app real con una IA simulada (`e2e/fake_ai.py`) y recorren: crear la cuenta de administrador, cuestionario inicial, registrar con IA y sin ella, trabajar sin conexión, productos con etiqueta y código de barras, aprobar una solicitud de cuenta, ingrediente a mano, copiar, agua, bebidas, medidas y fotos, días de entreno, un entreno sin conexión, recordatorios, plan y lista de la compra, cerrar el día, compartir la semana, importar un CSV y los atajos. Comprueban además que la IA se llama exactamente las veces esperadas.

**Lighthouse**, siempre en primera visita y sin caché:

| Medición | Rendimiento | Accesibilidad | Buenas prácticas |
|---|---|---|---|
| Las cinco pantallas con sesión y datos, móvil simulado (red lenta, CPU ×4), en local | 90 – 93 | 100 | 100 |
| Pantalla de acceso en producción, escritorio | 98 | 100 | 100 |

## Pendiente

Lo que queda, en orden (estado del 16 de octubre de 2026, por la tarde):

1. **Copia de seguridad fuera del servidor: falta la cuenta del dueño.** Hoy todas las copias viven en la misma VPS. Se eligió **Backblaze B2** (10 GB gratis, sin tarjeta). El dueño crea:
   - un bucket privado (por ejemplo `kcalia-copias-…`) y apunta su *endpoint* (`s3.<región>.backblazeb2.com`);
   - una *Application Key* limitada a ese bucket, con permiso *Read and Write*;
   - una frase de cifrado larga, guardada en su gestor de contraseñas.

   Después:
   - `.env`: `BACKUP_REMOTE_URL=https://s3.<región>.backblazeb2.com`, `BACKUP_REMOTE_BUCKET=<bucket>` y `BACKUP_REMOTE_REGION=<región>`. No son secretos.
   - Los secretos los mete el dueño, sin que pasen por el chat: `ssh -t root@161.97.67.178 /opt/kcalia/scripts/set-ai-key.sh BACKUP_REMOTE_ACCESS_KEY`, y lo mismo con `BACKUP_REMOTE_SECRET_KEY` y `BACKUP_ENCRYPTION_KEY`.
   - `docker compose up -d app`. Para comprobarlo: `backupcheck.run(...)` debe dar `remote` con la clave de la copia subida.
2. **Doble factor (TOTP), aprobado por el dueño y sin empezar.** Diseño previsto:
   - Columnas en `users`, con migración v5: `totp_secret`, `totp_enabled`, `totp_last_step` (contra reutilizar un código) y `recovery_codes`, que son 10 códigos guardados como SHA-256.
   - El login acepta un `code` opcional. Si la cuenta tiene doble factor y falta el código, responde `401` con `code: "totp_required"`; un código erróneo cuenta en el freno de intentos. Se admite un paso de margen (±30 s).
   - En Ajustes → Cuenta, el usuario lo activa y desactiva confirmando su contraseña. Ve un código QR (un SVG generado en el servidor, por ejemplo con `segno`) y un código para escribir a mano, confirma con un primer código y recibe los códigos de recuperación, que se muestran una sola vez.
   - Obligatorio para el administrador: sin él, `/api/admin/*` responde que lo active. Habrá un script de emergencia `scripts/disable-2fa.py` para usarlo por ssh.
3. *(Hecho el 16 de octubre: el cuestionario inicial elige el nivel de actividad con dos preguntas, en `frontend/src/lib/activity.ts`.)*
4. **Lista de errores en la pantalla del panel.** La API ya los da (`errors.recent`) y el estado de la comprobación de copias (`backup.check`); falta pintarlos en `Admin.tsx`.
5. **Revocar la clave del proveedor de IA anterior** en su consola. Lo hace el dueño.
6. **Fotos.** El error mediano de calorías con foto es del 41 % (`app.bench_photos`). Si se toca `PHOTO_INSTRUCTIONS`, conviene validarlo con otra muestra (`scripts/fetch_nutrition5k.py --seed` distinta).
7. **Exportación.** El JSON no incluye las fotos de progreso ni las imágenes de los productos.

**Notas para quien continúe:**
- Producción: `root@161.97.67.178` (`/opt/kcalia`). Se despliega con `./deploy/deploy.sh`, que hace pull de `main`, build, `up -d` y el bloque de Caddy.
- Claves: siempre con `scripts/set-ai-key.sh`, que las pide sin mostrarlas. Nunca se leen ni se imprimen los valores de `.env`.
- Otros proyectos: en la VPS hay otros proyectos en sus contenedores (`mosca`, `panel-*`, `horario-*`). No se paran ni se tocan.
- Ajustes del sistema: los de seguridad de la VPS (SSH, cortafuegos, fail2ban) los aplica el dueño con los scripts de `deploy/`.
- Antes de subir, pasan todas las suites (ver [Desarrollo y pruebas](#desarrollo-y-pruebas)).

## Roadmap

Hecho en la versión 2:

- [x] Añadir un ingrediente a mano dentro de una comida
- [x] Escáner de códigos de barras con Open Food Facts
- [x] Copiar un día entero o una comida a otro día
- [x] Recordatorios para registrar y para pesarse
- [x] Objetivos distintos para días de entrenamiento y de descanso
- [x] Fibra, agua y alcohol
- [x] Copia de seguridad fuera del servidor
- [x] Importar datos desde otras apps
- [x] Registro de entrenos, medidas y fotos de progreso
- [x] Plan semanal, lista de la compra y sugerencia para cerrar el día
- [x] Varias cuentas con aprobación y panel de administración

Hecho después:

- [x] Tabla oficial de alimentos (CIQUAL 2025 y USDA) con la IA solo para identificar y pesar
- [x] Gasto real medido con lo apuntado y el peso
- [x] Calorías netas del entreno con los MET del Compendium 2024

- [x] Claude Haiku 5.5 como modelo de IA (texto y fotos), medido frente al anterior
- [x] Días de descanso que compensan los de entreno y nivel de actividad «Medio»
- [x] Cambio de contraseña, freno en las confirmaciones, fuzzing de toda la API, escrituras simultáneas sin errores y aviso en vez de pantalla en blanco
- [x] Avisos de errores 500, de caídas de la web y comprobación semanal de las copias
- [x] Nivel de actividad elegido con dos preguntas («¿cómo es tu día?» y «¿cuántos días entrenas?»)

Ideas para más adelante:

- [ ] Ciclos de objetivos (por ejemplo, ocho semanas de definición y dos de mantenimiento)
- [ ] Recetas con raciones a partir de los ingredientes
- [ ] Exportar a Apple Salud y Health Connect

## Licencia

[MIT](LICENSE) © 2026 Álvaro Rovira

Datos de composición de alimentos: «Anses. 2025. Table de composition nutritionnelle des aliments Ciqual» (Licence Ouverte) y U.S. Department of Agriculture, FoodData Central (dominio público). Detalle y forma de regenerar los extractos en [`backend/app/data/FUENTES.md`](backend/app/data/FUENTES.md).
