# Cahier des charges --- Application locale d'aide à la résolution du solitaire

**Version :** 1.0\
**Plateforme cible initiale :** Windows\
**Mode d'exécution :** local, sans abonnement ni service payant
obligatoire

## 1. Contexte et objectif

Développer une application locale qui aide l'utilisateur à résoudre une
partie de solitaire Klondike. L'application ne doit pas remplacer le jeu
réel : l'utilisateur joue sur son jeu habituel et l'application lui
recommande des coups. L'utilisateur exécute le coup sur son jeu réel,
puis confirme dans l'application ce qu'il a fait. L'application met
alors à jour l'état de la partie et recalcule les recommandations.

L'objectif prioritaire est de trouver une ou plusieurs séquences menant
à la victoire. Si aucune victoire n'est trouvée dans le temps imparti,
l'application doit présenter les meilleures séquences partielles
identifiées, en privilégiant notamment les coups qui révèlent des cartes
cachées et ceux qui rapprochent les cartes des fondations.

## 2. Règles du jeu à prendre en charge

L'application doit implémenter le Klondike standard selon les règles
suivantes. Toute différence de variante doit être signalée avant d'être
codée, plutôt que résolue par une supposition silencieuse.

### 2.1 Tableau initial

-   Le tableau comporte **7 colonnes**.
-   Les colonnes contiennent respectivement 1, 2, 3, 4, 5, 6 et 7
    cartes, soit 28 cartes au total.
-   Dans chaque colonne, seule la carte du dessus est initialement face
    visible ; les autres sont face cachée.
-   L'utilisateur saisit l'identité des 7 cartes initialement visibles.
-   Les 24 cartes restantes sont dans la pioche (stock), dont
    l'utilisateur fournit la liste complète dans l'ordre exact.

> Important : la distribution standard décrite ici correspond à sept
> colonnes. Ne pas implémenter huit colonnes. Si l'utilisateur souhaite
> ultérieurement une autre variante, elle devra faire l'objet d'une
> évolution distincte.

### 2.2 Identité des cartes et inventaire

-   Un jeu contient 52 cartes uniques : 13 valeurs par couleur, pour les
    quatre couleurs.
-   Chaque carte est identifiée sans ambiguïté par sa valeur et sa
    couleur.
-   Les cartes de la pioche doivent être conservées dans l'ordre exact
    communiqué par l'utilisateur.
-   L'application doit empêcher l'affectation d'une même carte à
    plusieurs emplacements.
-   Les cartes initialement visibles, celles de la pioche, celles
    révélées ensuite, celles de la défausse et celles des fondations
    doivent partager un inventaire central cohérent.
-   Lorsqu'une carte cachée est retournée dans une colonne,
    l'application demande à l'utilisateur de l'identifier à l'aide d'un
    jeu visuel de 52 cartes. Les cartes déjà attribuées à un autre
    emplacement ne doivent plus être sélectionnables.
-   Si l'utilisateur ne connaît pas l'identité d'une carte révélée, il
    doit pouvoir reporter sa saisie. L'application ne doit jamais
    inventer sa valeur. Elle peut suspendre les recommandations qui
    dépendent de cette carte ou, si cela est techniquement raisonnable,
    gérer explicitement plusieurs hypothèses.

### 2.3 Déplacements dans le tableau

-   Dans le tableau, les cartes sont empilées par ordre décroissant.
-   Deux cartes consécutives dans une séquence doivent alterner entre
    rouge et noir.
-   Une séquence face visible peut être déplacée en bloc si le
    déplacement respecte les règles.
-   Une colonne vide ne peut recevoir qu'un roi, ou une séquence dont la
    première carte est un roi.
-   Lorsqu'une carte face cachée devient la carte supérieure d'une
    colonne après un déplacement, elle est retournée et l'application
    demande immédiatement à l'utilisateur de l'identifier.

### 2.4 Fondations

-   Il existe quatre fondations, une par couleur.
-   Chaque fondation commence par un as, puis reçoit les cartes de la
    même couleur dans l'ordre croissant jusqu'au roi.
-   Une carte envoyée dans une fondation ne peut **jamais être retirée
    de celle-ci**. Cette contrainte est absolue dans le moteur de règles
    et dans le solveur.

### 2.5 Pioche et défausse

-   La pioche est parcourue une carte à la fois.
-   La carte piochée rejoint la défausse ; seule la carte du dessus de
    la défausse est jouable.
-   Lorsque la pioche est vide, l'utilisateur peut retourner la défausse
    pour reformer la pioche.
-   Les retournements de la défausse sont illimités.
-   L'ordre exact des cartes pendant les retournements doit être défini,
    testé et documenté conformément à la variante retenue. Le solveur ne
    doit jamais réordonner librement les cartes de la pioche : il doit
    respecter leur ordre fourni et les règles de circulation entre
    pioche et défausse.

### 2.6 Condition de victoire

La partie est gagnée lorsque les 52 cartes ont été placées dans les
quatre fondations, conformément aux règles ci-dessus.

## 3. Saisie initiale de la partie

L'application doit proposer un écran de configuration initiale simple et
guidé.

L'utilisateur doit pouvoir : 1. sélectionner les sept cartes face
visible du tableau ; 2. saisir les 24 cartes de la pioche dans leur
ordre exact ; 3. visualiser le tableau et la pioche tels qu'ils ont été
saisis ; 4. corriger une carte avant de démarrer la recherche ; 5.
valider la cohérence de l'inventaire avant le lancement du solveur.

Les cartes déjà sélectionnées doivent être désactivées dans les autres
emplacements afin d'éviter les doublons. Les erreurs de saisie doivent
être expliquées clairement.

La première version concerne une partie initiale standard. La saisie
d'un état de partie arbitraire déjà commencé pourra être ajoutée
ultérieurement ; elle n'est pas indispensable à la première version.

## 4. Fonctionnalités principales

### 4.1 Affichage de la partie

L'interface doit présenter clairement : - les sept colonnes du tableau
; - les cartes cachées et les cartes visibles ; - la pioche et la
défausse ; - les quatre fondations ; - l'état courant de la partie ; -
les actions disponibles et les messages de validation.

L'interface doit rester simple, lisible et fonctionnelle, sans surcharge
visuelle.

### 4.2 Recherche de solutions

L'utilisateur peut lancer la recherche, l'interrompre manuellement et la
relancer après une mise à jour de l'état de la partie.

Le solveur doit : - chercher prioritairement des séquences qui gagnent
la partie ; - pouvoir trouver plusieurs solutions distinctes lorsque
cela est possible ; - respecter strictement les règles du jeu, l'ordre
de la pioche et l'interdiction de retirer une carte des fondations ; -
éviter de revisiter inutilement des états identiques, par exemple à
l'aide d'une mémorisation des états déjà explorés ; - comparer les
séquences candidates et classer les recommandations selon des critères
explicités ; - conserver les meilleures séquences partielles trouvées si
aucune victoire n'est identifiée dans le délai ; - distinguer clairement
une victoire trouvée, une recherche interrompue, un délai atteint et une
impossibilité effectivement démontrée.

Le choix de l'algorithme appartient au développeur. Il doit être
justifié brièvement dans la documentation et testé sur des cas connus.
Il peut combiner recherche en profondeur, mémorisation d'états,
heuristiques et recherche de plusieurs branches. Les heuristiques ne
doivent pas être présentées comme une preuve de victoire ou
d'impossibilité.

### 4.3 Classement des recommandations

Afficher plusieurs options classées, quand elles existent. Le classement
doit privilégier : 1. les séquences qui mènent à une victoire complète ;
2. les séquences qui révèlent des cartes cachées ; 3. les séquences qui
rendent des cartes accessibles ou libèrent une colonne ; 4. les
séquences qui permettent d'alimenter les fondations sans enfreindre les
règles ; 5. la progression globale vers la victoire, selon des critères
définis et documentés.

Pour chaque option, expliquer brièvement pourquoi elle est proposée :
carte révélée, colonne libérée, carte accessible, fondation avancée, ou
autre bénéfice mesurable. Ne pas présenter un score heuristique comme
une probabilité réelle de gagner, sauf si cette probabilité est
effectivement calibrée et justifiée.

### 4.4 Limite de temps de recherche

Le budget est de **200 secondes de calcul actif de recherche**.

Le décompte doit : - commencer uniquement lorsque l'utilisateur lance
effectivement une recherche ; - mesurer le temps consacré au calcul du
solveur ; - exclure l'installation, la préparation de l'environnement,
la saisie initiale, les déplacements réalisés par l'utilisateur sur son
jeu réel et le temps que celui-ci met à identifier une carte révélée ; -
être suspendu lorsque l'application attend une intervention ou une
confirmation de l'utilisateur ; - permettre l'arrêt manuel de la
recherche ; - arrêter la recherche lorsque le budget actif est consommé
et afficher les meilleurs résultats déjà obtenus.

Le temps écoulé et le temps de calcul actif doivent être distingués si
nécessaire. Le délai ne doit pas être appliqué à l'ensemble de la
session utilisateur.

### 4.5 Résultats partiels

Si aucune solution gagnante n'a été trouvée dans les 200 secondes de
calcul actif : - afficher les meilleures séquences partielles trouvées
; - indiquer le nombre d'états explorés, la durée de calcul actif et le
nombre de solutions gagnantes trouvées ; - afficher les progrès
mesurables, notamment les cartes révélées et les cartes placées dans les
fondations ; - expliquer les critères utilisés pour classer les
séquences partielles ; - préciser que « aucune solution trouvée dans le
délai » ne signifie pas nécessairement « partie impossible à gagner ».

Ne jamais inventer un pourcentage d'avancement si le solveur ne peut pas
le calculer de façon fiable.

## 5. Interaction avec le jeu réel

L'application sert de guide ; elle ne joue pas automatiquement sur le
jeu réel.

### 5.1 Confirmation d'un coup recommandé

Pour chaque coup recommandé, l'utilisateur doit pouvoir lire : - la
carte ou la séquence à déplacer ; - l'emplacement de départ ; -
l'emplacement de destination ; - une explication courte ; - les effets
attendus, notamment une carte qui devrait être révélée.

L'utilisateur exécute le coup sur son jeu réel, puis confirme dans
l'application le déplacement effectivement réalisé. L'application ne
doit jamais supposer qu'une recommandation a été exécutée simplement
parce qu'elle l'a affichée.

### 5.2 Coup différent ou coup manuel

Si l'utilisateur ne souhaite pas appliquer les options proposées, il
doit pouvoir saisir le coup qu'il a choisi : - sélectionner la carte ou
la séquence concernée ; - choisir la colonne ou la fondation de
destination ; - ou confirmer une action de pioche/retournement conforme
aux règles.

Le moteur doit vérifier la légalité du coup. Si le coup est illégal,
expliquer l'erreur et conserver l'état précédent.

Après chaque coup confirmé, l'application met à jour l'état du jeu et
recalcule les recommandations lorsque cela est nécessaire.

### 5.3 Révélation d'une carte

Lorsqu'un coup confirmé fait apparaître une carte jusque-là cachée : 1.
suspendre les recommandations qui nécessitent cette identité ; 2.
demander à l'utilisateur de sélectionner la carte dans le jeu visuel de
52 cartes ; 3. empêcher le choix d'une carte déjà affectée à un autre
emplacement ; 4. valider l'inventaire ; 5. reprendre ou relancer la
recherche à partir de l'état mis à jour.

Le temps passé à identifier la carte par l'utilisateur ne compte pas
dans les 200 secondes de calcul actif.

## 6. Lecture et navigation dans une séquence

Pour consulter une solution ou une séquence partielle, prévoir : -
**Précédent** ; - **Suivant** ; - **Lecture automatique** ; - **Pause**
; - **Recommencer la lecture**.

L'affichage doit permettre de comprendre l'état du jeu avant et après
chaque mouvement. La lecture d'une séquence de solution ne doit pas
modifier silencieusement l'état réel que l'utilisateur est en train de
confirmer.

## 7. Historique, annulation et correction

L'application doit conserver un historique des actions importantes : -
déplacements confirmés ; - actions de pioche et de retournement ; -
cartes révélées et identifiées ; - corrections de saisie ; - annulations
et restaurations.

L'utilisateur doit pouvoir annuler un coup ou revenir à un état
antérieur. La restauration doit rétablir de façon cohérente : -
l'emplacement de chaque carte ; - son statut visible ou caché ; -
l'ordre de la pioche et de la défausse ; - les fondations ; - les cartes
connues et les éventuelles identités encore inconnues ; - l'inventaire
central.

Toute modification qui invalide les recommandations existantes doit
marquer les résultats comme périmés et déclencher une nouvelle recherche
lorsque l'utilisateur le demande ou que le fonctionnement retenu le
prévoit. Ne jamais continuer à afficher un résultat périmé comme s'il
correspondait à l'état courant.

## 8. Informations de suivi pendant la recherche

Afficher au minimum : - l'état de la recherche : prête, en cours, en
pause en attente d'une saisie, arrêtée, délai atteint, victoire trouvée
ou erreur ; - le temps de calcul actif ; - le nombre d'états explorés
; - le nombre de séquences gagnantes trouvées ; - le meilleur nombre de
cartes dans les fondations atteint par une séquence partielle ; - le
nombre de cartes cachées révélées dans les meilleures séquences ; - la
meilleure séquence partielle disponible ; - les raisons principales du
classement des résultats.

Les statistiques doivent être calculées à partir de l'activité réelle du
solveur.

## 9. Architecture technique souhaitée

Préférence initiale : interface HTML/CSS/JavaScript avec backend Python,
mais le développeur peut proposer une architecture plus adaptée si elle
reste simple à exécuter localement sur Windows. Toute déviation doit
être justifiée brièvement.

Séparer logiquement : - les règles et la représentation des cartes ; -
l'état du jeu ; - la validation des coups ; - la pioche, la défausse et
les retournements ; - le solveur et ses heuristiques ; - l'inventaire
des cartes et les révélations ; - l'historique et l'annulation ; -
l'interface utilisateur ; - les tests.

L'application doit fonctionner localement, sans abonnement obligatoire
ni service cloud payant. Éviter les dépendances inutiles. Prévoir une
possibilité de déploiement en ligne ultérieure sans en faire une
exigence de la première version.

## 10. Installation et lancement sur Windows

Le développeur doit créer les fichiers nécessaires au projet, notamment
: - le code de l'application ; - `requirements.txt` avec les dépendances
nécessaires ; - `README.md` avec les prérequis et les commandes exactes
d'installation et de lancement ; - un script Windows `.cmd` adapté à
l'architecture effectivement choisie, si un lancement automatisé est
retenu ; - les tests automatisés.

Le script `.cmd` est un outil auxiliaire de lancement : **il ne remplace
pas le cahier des charges et ne crée pas le code applicatif**. Il doit
utiliser le bon point d'entrée documenté, et ne pas deviner entre
plusieurs architectures incompatibles.

L'environnement virtuel local `.venv` est recommandé afin d'isoler les
dépendances du projet. Le script de lancement doit être adapté à la
commande réelle décrite dans le `README.md`.

## 11. Étapes de travail attendues du développeur

Le développeur ou agent de programmation doit suivre cet ordre :

1.  Inspecter le dossier de travail fourni avant de modifier quoi que ce
    soit.
2.  Signaler les fichiers existants et préserver les éléments utiles ;
    ne pas écraser de fichiers sans raison.
3.  Reformuler les règles confirmées et signaler toute ambiguïté qui
    nécessite une décision.
4.  Proposer brièvement l'architecture et l'approche de recherche.
5.  Mettre en place l'environnement local et les dépendances.
6.  Développer l'application par composants séparés.
7.  Ajouter les tests automatisés et les exécuter.
8.  Lancer l'application localement et vérifier les fonctions
    essentielles.
9.  Corriger les erreurs détectées.
10. Fournir un compte rendu : fichiers créés, commande de lancement,
    tests exécutés et résultats, limites connues et points restant à
    traiter.

Ne pas déclarer une fonctionnalité terminée si elle n'a pas été
implémentée et testée.

## 12. Tests d'acceptation

Les tests doivent couvrir au minimum :

### Règles et cartes

-   exactement 52 cartes uniques dans l'inventaire ;
-   validation des sept colonnes et des 28 cartes du tableau initial ;
-   respect de l'ordre exact des 24 cartes de la pioche ;
-   détection des doublons et des cartes manquantes ;
-   déplacements légaux et illégaux selon l'alternance des couleurs et
    l'ordre décroissant ;
-   déplacement d'une séquence ;
-   placement d'un roi sur une colonne vide ;
-   progression des fondations par couleur ;
-   impossibilité de retirer une carte d'une fondation.

### Pioche et défausse

-   pioche d'une carte ;
-   accessibilité de la seule carte supérieure de la défausse ;
-   retournement de la défausse lorsque la pioche est vide ;
-   nombre illimité de retournements ;
-   ordre cohérent des cartes lors de chaque retournement.

### Révélations et inventaire

-   révélation d'une carte après déplacement ;
-   impossibilité d'affecter une carte déjà utilisée ;
-   suspension pendant l'attente de l'identification ;
-   reprise après identification ;
-   aucune identité inventée si l'utilisateur reporte la saisie.

### Solveur

-   respect des règles dans toutes les séquences produites ;
-   reconnaissance d'une victoire ;
-   distinction entre solution gagnante et solution partielle ;
-   mémorisation ou déduplication d'états, si cette optimisation est
    retenue ;
-   arrêt manuel ;
-   respect du budget de 200 secondes de calcul actif ;
-   conservation des meilleurs résultats partiels à l'arrêt ;
-   aucune affirmation d'impossibilité lorsque seule la limite de temps
    a été atteinte.

### Historique et interface

-   confirmation d'un coup réellement exécuté ;
-   rejet d'un coup illégal sans corruption de l'état ;
-   annulation et restauration complètes ;
-   invalidation des résultats de recherche devenus périmés ;
-   navigation précédente/suivante et lecture/pause/recommencement d'une
    séquence.

## 13. Critères de livraison

La première version est considérée comme livrée lorsque : -
l'application démarre localement sur Windows avec une procédure
documentée ; - la saisie initiale et le contrôle des cartes fonctionnent
; - les règles essentielles sont appliquées et testées ; - l'utilisateur
peut lancer et interrompre la recherche ; - les solutions gagnantes et
les séquences partielles sont présentées honnêtement ; - l'utilisateur
peut confirmer ses coups et identifier les cartes révélées ; -
l'historique et les corrections préservent la cohérence de l'état ; -
les tests essentiels ont été exécutés et leurs résultats sont rapportés
; - la documentation indique les limites connues.

## 14. Principes non négociables

-   Ne jamais inventer l'identité d'une carte.
-   Ne jamais modifier librement l'ordre initial de la pioche.
-   Ne jamais retirer une carte d'une fondation.
-   Ne jamais considérer un coup recommandé comme exécuté sans
    confirmation de l'utilisateur.
-   Ne jamais présenter un dépassement du délai comme une preuve que la
    partie est impossible.
-   Ne jamais présenter des statistiques estimées comme des mesures
    réelles.
-   Ne pas imposer de service payant ou d'abonnement obligatoire.
-   Privilégier une application fonctionnelle, vérifiable et explicable
    plutôt qu'une interface complexe.
