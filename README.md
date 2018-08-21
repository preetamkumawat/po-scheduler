# Purchase Order Scheduler

```
Takes in PurchaseOrders as Input and decides which dock should it be inbounded to
```

This code contains mainly 4 files:
1. **app.py** - This contains the front end APIs. Runs a flask app
2. **scheduler.py** - Holds the core logic for dock assignment and other stuff
3. **utils.py** - Takes care of the db connection part.
4. **models.py** - Holds rough implementation of the entities and their properties.

## Running the code
Please type in the below command after navigating in terminal to directory named **PurchaseOrderScheduler**

``` 
pip install -r requirements.txt
python app.py
```

## Environment Variables:
>*Four Envionment variables are required in Order to run the code*
```
DB_USER
DB_PASSWORD
DB_HOST
DB_PORT
```

> The output files (***po_schedular_output.csv***, ***slot_performances.csv***) should be available outside Directory PurchaseOrderScheduler

