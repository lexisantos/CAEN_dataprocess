# CAEN_dataprocess
Procesamiento de datos .ROOT y .BIN exportados desde un digitalizador CAEN.

En caso de querer procesar .ROOT, se recomienda crear un nuevo environment e [instalar ROOT](https://root.cern/install/) en él.

* ***process_bin_root.py***: compilación de funciones para procesar archivos .ROOT y .BIN, clasificar carpetas y archivos según contenido, hacer gráficos, aplicar calibraciones, encontrar coincidencias.
* ***analyze_bin_root.ipynb***: define el análisis más general (histogramas + coincidencias) **usar este para extraer gráficos por run**.

* ***calibracion_energy.ipynb***: notebook para realizar calibraciones a partir de histogramas con picos (ajuste lineal).
* ***modelling_data.py***: define un modelo lineal a partir de LinearRegression de scikit-learn.
* ***analyze_one_case.ipynb***: notebook que estructura el procesamiento y visualización de los datos de **una experiencia** usando las funciones definidas en *process_bin_root.py*.
