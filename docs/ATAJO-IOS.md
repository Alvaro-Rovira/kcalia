# Atajo de voz en iPhone

Apunta una comida hablando con Siri («Oye Siri, apuntar en Kcalia») sin abrir antes la app. Se configura una vez en
la app **Atajos**. La misma guía está en Kcalia → Ajustes → Atajos → «Atajo de voz en iPhone», con la dirección de tu
servidor lista para copiar.

## Pasos

1. Abre **Atajos**, pulsa **+** y llama al atajo **Apuntar en Kcalia** (es la frase que dirás a Siri).
2. Añade la acción **Dictar texto** (idioma: español).
3. Añade **Codificar URL** (en algunas versiones, «Codificar o descodificar URL») sobre el texto dictado.
4. Añade la acción **URL** con `https://TU-DOMINIO/?nueva=1&texto=` y, justo detrás, la variable del texto codificado.
5. Añade **Abrir URLs** y guarda.
6. Di «Oye Siri, apuntar en Kcalia», cuenta qué has comido, revisa el texto y pulsa **Analizar**.

## Cómo funciona

- `/?nueva=1&texto=...` abre la hoja de añadir comida con el texto ya escrito (máximo 600 caracteres). **No se
  analiza solo**: un enlace no puede gastar IA sin que pulses «Analizar».
- iOS abre los enlaces de los atajos en Safari, no en la app de la pantalla de inicio (cada una tiene su sesión): la
  primera vez inicia sesión también en Safari.

## Atajos de la app instalada (Android y escritorio)

Mantén pulsado el icono de Kcalia (o clic derecho en el escritorio):

| Atajo | URL | Qué hace |
| --- | --- | --- |
| Añadir comida | `/?nueva=1` | Abre la hoja de añadir |
| Un vaso de agua | `/?agua=250` | Apunta 250 ml hoy, con «Deshacer» (acepta de 50 a 1000 ml) |
| Entrenar | `/entreno` | Abre el registro de entrenos |
| Apuntar peso | `/peso` | Abre el peso y las medidas |

iOS no muestra estos atajos del manifiesto; ahí se usa el atajo de voz.
